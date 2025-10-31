#!/usr/bin/env python
"""
Ingestion Pipeline CLI Tool V1
Processes PDFs with deduplication, quarantine, and doc_id mapping
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger

from app.ingestion.document_classifier import DocumentClassifier
from app.ingestion.paddle_ocr_config import get_ocr_status
from app.ingestion.pdf_processor import PageContent, PDFDocument, PDFProcessor
from app.rag.chunkers.hierarchical_chunker import HierarchicalChunker
from app.storage.manifest_writer import ManifestWriter
from app.storage.version_manager import VersionManager

# P&ID tag extraction (optional)
try:
    from app.ingestion.tags.orchestrator import TagExtractionOrchestrator

    PID_TAGS_AVAILABLE = True
except ImportError:
    PID_TAGS_AVAILABLE = False
    logger.warning("P&ID tag extraction components not available")


class IngestionPipeline:
    """
    Multithreaded ingestion pipeline for PDF processing with deduplication
    """

    def __init__(
        self,
        source_dir: Path,
        output_dir: Path,
        workers: int = None,
        enable_ocr: bool = False,
        ocr_language: str = "eng",
        parser: str = "auto",
        emit_jsonl: bool = True,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        chunk_strategy: str = "hierarchical",
        sentence_window_size: int = 3,
        use_llm_classifier: bool = False,
        llm_model: Optional[str] = None,
        extract_tables: bool = True,
        table_min_rows: int = 2,
        table_min_cols: int = 2,
        create_version: bool = False,
        version_id: Optional[str] = None,
        version_description: str = "",
        version_tags: Optional[List[str]] = None,
        enable_pid_tags: bool = False,
    ):
        """
        Initialize ingestion pipeline

        Args:
            source_dir: Directory containing PDFs to process
            output_dir: Directory for outputs
            workers: Number of worker threads (None for auto)
            enable_ocr: Enable OCR for scanned pages
            ocr_language: Language for OCR (vie+eng for Vietnamese & English)
            parser: Parser to use ('auto', 'pymupdf', 'unstructured')
            emit_jsonl: Emit JSONL outputs in addition to JSON
            chunk_size: Target chunk size
            chunk_overlap: Overlap between chunks
            create_version: Automatically create version snapshot after ingestion
            version_id: Version identifier (default: auto-generated from timestamp)
            version_description: Human-readable version description
            version_tags: Optional tags for version categorization
        """
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)

        # Default workers for Windows safety
        if workers is None:
            workers = min(4, os.cpu_count() or 4)
        self.workers = workers

        # OCR settings
        self.enable_ocr = enable_ocr
        self.ocr_language = ocr_language

        # Table extraction settings
        self.extract_tables = extract_tables
        self.table_min_rows = table_min_rows
        self.table_min_cols = table_min_cols

        # Parser settings
        self.parser = parser
        self.emit_jsonl = emit_jsonl

        # Chunking settings
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_strategy = chunk_strategy
        self.sentence_window_size = sentence_window_size
        self.use_llm_classifier = use_llm_classifier
        self.llm_model = llm_model

        # Versioning settings
        self.create_version = create_version
        self.version_id = version_id
        self.version_description = version_description
        self.version_tags = version_tags or []

        # P&ID tag extraction settings
        self.enable_pid_tags = enable_pid_tags and PID_TAGS_AVAILABLE

        # Initialize document classifier
        self.classifier = DocumentClassifier()

        # Initialize P&ID tag extraction orchestrator (if enabled)
        self.tag_orchestrator = None
        if self.enable_pid_tags:
            try:
                self.tag_orchestrator = TagExtractionOrchestrator(
                    enable_crops=True,
                    lazy_crops=True,  # Don't generate crops during ingestion for speed
                )
                logger.info("✅ P&ID tag extraction enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize P&ID tag extraction: {e}")
                self.enable_pid_tags = False

        # Thread-safe locks
        self._jsonl_lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self._quarantine_lock = threading.Lock()
        self._dedup_lock = threading.Lock()

        # Deduplication tracking
        self.content_hash_map = {}  # content_hash -> representative doc
        self.duplicate_groups = {}  # content_hash -> list of duplicates
        self.file_hash_seen = set()  # Track file hashes to skip exact duplicates

        # Track processing stats
        self.stats = {
            "total_pdfs": 0,
            "processed": 0,
            "failed": 0,
            "duplicates_skipped": 0,  # Exact file duplicates (100% identical)
            "ocr_count": 0,
            "duplicates_collapsed": 0,
            "quarantine_count": 0,
            "scanned_pages": 0,
            "vector_pages": 0,
            "total_chunks": 0,
            "pid_docs_processed": 0,  # P&ID documents processed
            "pid_tags_extracted": 0,  # Total P&ID tags extracted
            "start_time": None,
            "end_time": None,
        }

        # Run ID for batch tracking
        self.run_id = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _setup_output_dirs(self):
        """Create necessary output directories"""
        dirs = [
            self.output_dir,
            self.output_dir / "documents",
            self.output_dir / "markdown",
            self.output_dir / "chunks",
            self.output_dir / "manifests",
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def run(self) -> Dict[str, Any]:
        """
        Run the ingestion pipeline

        Returns:
            Processing statistics
        """
        logger.info("=" * 80)
        logger.info("Starting Ingestion Pipeline V1")
        logger.info(f"Source: {self.source_dir}")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Workers: {self.workers}")
        logger.info(f"OCR: {self.enable_ocr} (lang: {self.ocr_language})")
        logger.info(
            f"Tables: {self.extract_tables} (min: {self.table_min_rows}x{self.table_min_cols})"
        )
        logger.info(f"Parser: {self.parser}")
        logger.info(f"Chunk strategy: {self.chunk_strategy}")
        logger.info(f"Run ID: {self.run_id}")
        logger.info("=" * 80)

        self.stats["start_time"] = datetime.now()

        # Ensure output directories exist
        self._setup_output_dirs()

        # Find all PDFs recursively
        pdf_files = list(self.source_dir.rglob("*.pdf"))
        self.stats["total_pdfs"] = len(pdf_files)

        if not pdf_files:
            logger.warning("No PDF files found in source directory")
            return self.stats

        logger.info(f"Found {len(pdf_files)} PDF files to process")

        # Initialize manifests
        corpus_manifest = []
        checksums_manifest = []
        doc_id_map = {}
        table_index = []  # Global table index for all tables across documents

        # Process PDFs in parallel
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # Submit all tasks
            future_to_pdf = {
                executor.submit(self._process_single_pdf, pdf_path): pdf_path
                for pdf_path in pdf_files
            }

            # Collect results
            for future in as_completed(future_to_pdf):
                pdf_path = future_to_pdf[future]

                try:
                    result = future.result()
                    if result:
                        if result["status"] == "processed":
                            corpus_entry = result["corpus_entry"]
                            checksum_entry = result["checksum_entry"]
                            counts = result["counts"]

                            corpus_manifest.append(corpus_entry)
                            checksums_manifest.append(checksum_entry)
                            doc_id_map[corpus_entry["doc_id"]] = str(pdf_path)

                            # Collect table metadata if available
                            if "table_metadata" in result and result["table_metadata"]:
                                table_index.extend(result["table_metadata"])

                            # Update stats
                            self.stats["processed"] += 1
                            self.stats["total_chunks"] += counts.get("chunks", 0)
                            self.stats["scanned_pages"] += counts.get(
                                "scanned_pages", 0
                            )
                            self.stats["vector_pages"] += counts.get("vector_pages", 0)
                            if counts.get("used_ocr", False):
                                self.stats["ocr_count"] += 1

                            # Track chunk size distribution for analytics
                            if "chunk_sizes" not in self.stats:
                                self.stats["chunk_sizes"] = []
                            if "chunk_sizes" in counts:
                                self.stats["chunk_sizes"].extend(counts["chunk_sizes"])

                            logger.info(
                                f"[{self.stats['processed']}/{self.stats['total_pdfs']}] "
                                f"Processed: {pdf_path.name}"
                            )
                        elif result["status"] == "skipped":
                            # Already counted in duplicates_skipped
                            logger.debug(
                                f"Skipped: {pdf_path.name} - {result.get('reason', 'unknown')}"
                            )
                        elif result["status"] == "duplicate":
                            self.stats["duplicates_collapsed"] += 1
                            logger.info(f"Skipped duplicate: {pdf_path.name}")
                        elif result["status"] == "quarantine":
                            self.stats["quarantine_count"] += 1
                            logger.warning(
                                f"Quarantined: {pdf_path.name} - {result['reason']}"
                            )

                except Exception as e:
                    logger.error(f"Failed to process {pdf_path.name}: {e}")
                    self.stats["failed"] += 1
                    self._add_to_quarantine(pdf_path, "processing_error", str(e))

        # Write manifests
        self._write_manifests(corpus_manifest, checksums_manifest)

        # Write doc_id_map.json
        self._write_doc_id_map(doc_id_map)

        # Write deduplication report
        self._write_dedup_report()

        # Write table index
        self._write_table_index(table_index)

        # Write ingestion manifest for versioning
        ingestion_manifest_path = self._write_ingestion_manifest()

        self.stats["end_time"] = datetime.now()
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        # Print summary
        logger.info("=" * 80)
        logger.info("Ingestion Pipeline Complete")
        logger.info(f"Total PDFs: {self.stats['total_pdfs']}")
        logger.info(f"Processed: {self.stats['processed']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(
            f"Duplicates skipped (exact files): {self.stats['duplicates_skipped']}"
        )
        logger.info(f"Duplicates collapsed: {self.stats['duplicates_collapsed']}")
        logger.info(f"Quarantined: {self.stats['quarantine_count']}")
        logger.info(f"Used OCR: {self.stats['ocr_count']}")
        logger.info(f"Total chunks: {self.stats['total_chunks']}")

        # P&ID extraction stats
        if self.enable_pid_tags:
            logger.info(f"P&ID documents processed: {self.stats['pid_docs_processed']}")
            logger.info(f"P&ID tags extracted: {self.stats['pid_tags_extracted']}")

        # Chunk size analytics
        if "chunk_sizes" in self.stats and self.stats["chunk_sizes"]:
            chunk_sizes = self.stats["chunk_sizes"]
            avg_size = sum(chunk_sizes) / len(chunk_sizes)
            min_size = min(chunk_sizes)
            max_size = max(chunk_sizes)
            logger.info(
                f"Chunk sizes: min={min_size}, max={max_size}, avg={avg_size:.0f}"
            )

        logger.info(f"Duration: {duration:.2f} seconds")
        if self.stats["processed"] > 0:
            logger.info(
                f"Throughput: {self.stats['processed']/duration:.2f} PDFs/second"
            )
        logger.info("=" * 80)

        # Create version snapshot if requested
        if self.create_version and self.stats["processed"] > 0:
            logger.info("")
            logger.info("Creating version snapshot...")
            self._create_version_snapshot(ingestion_manifest_path)

        return self.stats

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file bytes"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _calculate_content_hash(self, text: str) -> str:
        """
        Calculate SHA1 hash of normalized content
        Normalization: Unicode NFKC -> lowercase -> collapse whitespace -> remove line-ending hyphens -> strip
        """
        # Unicode normalization
        normalized = unicodedata.normalize("NFKC", text)

        # Lowercase
        normalized = normalized.lower()

        # Remove line-ending hyphens before collapsing whitespace
        normalized = normalized.replace("-\n", "").replace("-\r\n", "")

        # Collapse all whitespace (including newlines) to single spaces
        import re

        normalized = re.sub(r"\s+", " ", normalized)

        # Strip leading/trailing whitespace
        normalized = normalized.strip()

        # Calculate SHA1 hash
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def _select_representative(self, candidates: List[Dict]) -> Dict:
        """
        Select representative from duplicate candidates based on criteria:
        1. source_format=vector preferred over scan
        2. Larger file size
        3. Newer mtime
        4. Shorter path
        """

        def score_candidate(candidate):
            # Higher score = better representative
            score = 0

            # Prefer vector format
            if candidate.get("source_format") == "vector":
                score += 10000

            # Prefer larger file
            score += candidate.get("file_size", 0) / (1024 * 1024)  # In MB

            # Prefer newer file (mtime as timestamp)
            score += candidate.get("mtime", 0) / 1000000  # Scale down

            # Prefer shorter path (negative length)
            score -= len(candidate.get("file_path", "")) / 1000

            return score

        # Sort by score descending
        candidates.sort(key=score_candidate, reverse=True)
        return candidates[0]

    def _add_to_quarantine(self, file_path: Path, reason_code: str, detail: str = ""):
        """Add file to quarantine log"""
        quarantine_entry = {
            "file": str(file_path),
            "reason_code": reason_code,
            "detail": detail,
            "run_id": self.run_id,
            "ts": datetime.now().isoformat(),
        }

        quarantine_file = self.output_dir / "quarantine.jsonl"

        with self._quarantine_lock:
            with open(quarantine_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(quarantine_entry, ensure_ascii=False) + "\n")

    def _process_single_pdf(self, pdf_path: Path) -> Optional[Dict]:
        """
        Process a single PDF with deduplication check

        Returns:
            Dict with status and data
        """
        try:
            # Calculate file hash
            file_hash = self._calculate_file_hash(pdf_path)
            file_size = pdf_path.stat().st_size
            mtime = pdf_path.stat().st_mtime

            # ===== FILE HASH DEDUPLICATION =====
            # Skip exact file duplicates (100% identical files)
            with self._dedup_lock:
                if file_hash in self.file_hash_seen:
                    # This is an exact duplicate file
                    self.stats["duplicates_skipped"] += 1
                    logger.info(
                        f"Skipping exact duplicate (file_hash): {pdf_path.name}"
                    )
                    return {"status": "skipped", "reason": "exact_file_duplicate"}

                # Mark this file_hash as seen
                self.file_hash_seen.add(file_hash)
            # ===== END FILE HASH DEDUPLICATION =====

            # Try to extract text first
            pdf_doc = None
            used_ocr = False

            try:
                # Try without OCR first to detect if text is extractable
                processor = PDFProcessor(
                    enable_ocr=False,
                    ocr_language=self.ocr_language,
                    ocr_min_confidence=30.0,
                    extract_tables=self.extract_tables,
                    table_min_rows=self.table_min_rows,
                    table_min_cols=self.table_min_cols,
                )
                pdf_doc = processor.process_pdf(pdf_path)

                # Check if we need OCR (no text extracted)
                total_text = "".join(page.text for page in pdf_doc.pages)
                if (
                    self.enable_ocr and len(total_text.strip()) < 100
                ):  # Less than 100 chars
                    logger.info(
                        f"No vector text found, applying OCR to {pdf_path.name}"
                    )
                    processor = PDFProcessor(
                        enable_ocr=True,
                        ocr_language=self.ocr_language,
                        ocr_min_confidence=30.0,
                        extract_tables=self.extract_tables,
                        table_min_rows=self.table_min_rows,
                        table_min_cols=self.table_min_cols,
                    )
                    pdf_doc = processor.process_pdf(pdf_path)
                    used_ocr = True

            except Exception as e:
                # Document is corrupted or unreadable
                self._add_to_quarantine(pdf_path, "corrupt", str(e))
                return {"status": "quarantine", "reason": "corrupt"}

            # Get full text for content hashing
            full_text = "\n".join(page.text for page in pdf_doc.pages)

            if not full_text.strip():
                # No text could be extracted even with OCR
                self._add_to_quarantine(pdf_path, "ocr_failed", "No text extracted")
                return {"status": "quarantine", "reason": "ocr_failed"}

            # Calculate content hash (for tracking only, not for deduplication)
            content_hash = self._calculate_content_hash(full_text)

            # ===== CONTENT DEDUPLICATION DISABLED =====
            # Only file_hash deduplication is active (exact file duplicates)
            # Files with similar content (95-99% match) will be kept
            # This allows multiple versions of documents to coexist
            with self._dedup_lock:
                # COMMENTED OUT: Content-based deduplication
                # if content_hash in self.content_hash_map:
                #     # This is a duplicate
                #     if content_hash not in self.duplicate_groups:
                #         self.duplicate_groups[content_hash] = []
                #
                #     duplicate_info = {
                #         "file_path": str(pdf_path),
                #         "file_hash": file_hash,
                #         "file_size": file_size,
                #         "mtime": mtime,
                #         "source_format": pdf_doc.source_format,
                #     }
                #     self.duplicate_groups[content_hash].append(duplicate_info)
                #
                #     return {"status": "duplicate"}
                # else:
                #     # First occurrence of this content

                # Always process as unique content (only file_hash dedup remains active)
                representative_info = {
                    "file_path": str(pdf_path),
                    "file_hash": file_hash,
                    "file_size": file_size,
                    "mtime": mtime,
                    "source_format": pdf_doc.source_format,
                    "pdf_doc": pdf_doc,
                    "content_hash": content_hash,
                }
                self.content_hash_map[content_hash] = representative_info

            # Process the representative document
            # Generate doc_id
            doc_id = self._generate_doc_id(pdf_path, pdf_doc)

            # Detect document type and revision
            doc_type, revision = self._classify_document(pdf_path, pdf_doc)

            # Save processed document
            self._save_processed_document(pdf_doc, doc_id)

            # Convert to markdown
            markdown_text = self._convert_to_markdown(pdf_doc, doc_id)

            # Create chunks
            chunks = self._create_chunks(
                pdf_doc, markdown_text, doc_id, doc_type, revision
            )

            # Save chunks
            self._save_chunks(chunks, doc_id)

            # === P&ID TAG EXTRACTION ===
            # Extract instrument tags from CAD-like documents (P&ID, PFD, etc.)
            pid_result = None
            if self.enable_pid_tags and self.tag_orchestrator:
                try:
                    logger.debug(f"Running P&ID tag extraction for {pdf_path.name}")
                    pid_result = self.tag_orchestrator.process_document(
                        pdf_path, doc_id
                    )

                    if pid_result:
                        # Update stats (thread-safe)
                        with self._stats_lock:
                            self.stats["pid_docs_processed"] += 1
                            self.stats["pid_tags_extracted"] += pid_result.get(
                                "tags_extracted", 0
                            )

                        logger.info(
                            f"P&ID extraction: {pid_result.get('tags_extracted', 0)} tags "
                            f"from {pid_result.get('pages_processed', 0)} pages"
                        )
                    else:
                        logger.debug(
                            f"Document not identified as CAD-like: {pdf_path.name}"
                        )

                except Exception as e:
                    # Don't crash main pipeline on tag extraction errors
                    logger.warning(
                        f"P&ID tag extraction failed for {pdf_path.name}: {e}"
                    )
                    logger.debug(f"Tag extraction error details:", exc_info=True)
            # === END P&ID TAG EXTRACTION ===

            # Extract table metadata from chunks
            table_metadata = self._extract_table_metadata_from_chunks(chunks, doc_id)

            # Count pages by source_format
            scanned_count = pdf_doc.num_pages if pdf_doc.source_format == "scan" else 0
            vector_count = pdf_doc.num_pages if pdf_doc.source_format == "vector" else 0

            # Create manifest entries
            corpus_entry = {
                "doc_id": doc_id,
                "file_path": str(pdf_path),
                "hash_sha256": file_hash,
                "content_hash": content_hash,
                "pages": pdf_doc.num_pages,
                "doc_type": doc_type,
                "revision": revision,
                "source_format": pdf_doc.source_format,
                "ingested_at": datetime.now().isoformat(),
            }

            checksum_entry = {
                "file_path": str(pdf_path),
                "hash_sha256": file_hash,
                "content_hash": content_hash,
                "last_modified": int(mtime),
            }

            counts = {
                "chunks": len(chunks),
                "scanned_pages": scanned_count,
                "vector_pages": vector_count,
                "used_ocr": used_ocr,
                "chunk_sizes": [
                    chunk.get("char_count", 0) for chunk in chunks
                ],  # For analytics
            }

            return {
                "status": "processed",
                "corpus_entry": corpus_entry,
                "checksum_entry": checksum_entry,
                "counts": counts,
                "table_metadata": table_metadata,
            }

        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            self._add_to_quarantine(pdf_path, "read_error", str(e))
            return {"status": "quarantine", "reason": "read_error"}

    def _generate_doc_id(self, pdf_path: Path, pdf_doc: PDFDocument) -> str:
        """Generate safe, unique document ID (no path separators)"""
        import re
        import unicodedata

        # Use relative path from source_dir if possible
        try:
            rel_path = pdf_path.relative_to(self.source_dir)
            parts = list(rel_path.parts)
            if parts:
                parts[-1] = Path(parts[-1]).stem
            base_id = "_".join(parts)
        except Exception:
            base_id = pdf_path.stem

        # Normalize unicode and remove invalid characters for Windows filenames
        base_id = unicodedata.normalize("NFKD", base_id)
        # Replace any disallowed chars (anything not alnum, dot, underscore, hyphen) with underscore
        base_id = re.sub(r"[^A-Za-z0-9._-]+", "_", base_id)
        # Collapse multiple underscores
        base_id = re.sub(r"_+", "_", base_id).strip("_")
        # Truncate to reasonable length
        base_id = base_id[:80] if base_id else "document"

        # Add hash suffix for uniqueness
        hash_suffix = hashlib.md5(str(pdf_path).encode()).hexdigest()[:8]

        return f"DOCID_{base_id}_{hash_suffix}"

    def _classify_document(
        self, pdf_path: Path, pdf_doc: PDFDocument
    ) -> Tuple[str, Optional[str]]:
        """
        Classify document type and extract revision using enhanced classifier

        Returns:
            Tuple of (doc_type, revision)
        """
        # Get first page text if available
        first_page_text = None
        if pdf_doc.pages:
            first_page_text = pdf_doc.pages[0].text

        # Prepare metadata
        metadata = {
            "title": pdf_doc.title,
            "subject": pdf_doc.subject,
            "keywords": pdf_doc.keywords,
        }

        # Use the enhanced classifier
        if self.use_llm_classifier and self.llm_model:
            # Use LLM-enhanced classification (will fall back to rules if LLM fails)
            doc_type, revision = self.classifier.classify_with_llm(
                file_path=pdf_path,
                first_page_text=first_page_text,
                model_name=self.llm_model,
            )
        else:
            # Use rule-based classification only
            doc_type, revision = self.classifier.classify(
                file_path=pdf_path, first_page_text=first_page_text, metadata=metadata
            )

        return doc_type, revision

    def _save_processed_document(self, pdf_doc: PDFDocument, doc_id: str):
        """Save processed document as JSON"""
        output_file = self.output_dir / "documents" / f"{doc_id}_processed.json"

        # Use atomic write (temp file + rename)
        temp_file = output_file.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(pdf_doc.to_json())

        # Atomic rename
        temp_file.replace(output_file)

    def _convert_to_markdown(self, pdf_doc: PDFDocument, doc_id: str) -> str:
        """Convert PDF document to markdown with vector fallback for better headings"""
        markdown_text = ""
        structure_meta: Optional[Dict[str, Any]] = None

        try:
            from app.rag.converters.markdown_converter import MarkdownConverter

            converter = MarkdownConverter()

            # Check if we have tables - if so, use simple path to preserve them
            has_tables = any(page.tables for page in pdf_doc.pages if page.tables)

            use_vector = (
                self.parser in ("auto", "pymupdf")
                and pdf_doc.source_format == "vector"
                and not has_tables  # Don't use VectorExtractor if we have tables
            )

            if use_vector:
                try:
                    # Use VectorExtractor for structured extraction (better headings)
                    from app.rag.extractors.vector_extractor import VectorExtractor

                    extractor = VectorExtractor()
                    extraction = extractor.extract_with_structure(pdf_doc.file_path)
                    md_result = converter.convert_with_structure(extraction)
                    markdown_text = md_result["markdown"]
                    structure_meta = md_result.get("structure", {})
                except Exception as ve:
                    logger.warning(
                        f"VectorExtractor path failed, falling back to simple conversion: {ve}"
                    )

            if not markdown_text:
                # Simple conversion from pdf_doc pages
                extraction = {"file_path": pdf_doc.file_path, "pages": []}
                for page in pdf_doc.pages:
                    page_data = {
                        "page_num": (page.page_num - 1) if page.page_num else 0,
                        "full_text": page.text,
                        "blocks": [{"text": page.text, "structure_type": "paragraph"}],
                    }
                    # Add tables if present
                    if page.tables:
                        page_data["tables"] = page.tables
                    extraction["pages"].append(page_data)
                md_result = converter.convert_with_structure(extraction)
                markdown_text = md_result["markdown"]
                structure_meta = md_result.get("structure", {})
        except Exception as e:
            logger.warning(f"Markdown converter failed, using plain text: {e}")
            markdown_text = "\n\n".join(page.text for page in pdf_doc.pages)
            structure_meta = None

        # Save markdown (atomic write)
        md_file = self.output_dir / "markdown" / f"{doc_id}.md"
        temp_file = md_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        temp_file.replace(md_file)

        # Save structure metadata alongside, if available
        if structure_meta is not None:
            meta_path = md_file.with_suffix(".json")
            temp_meta = meta_path.with_suffix(".tmp")
            try:
                with open(temp_meta, "w", encoding="utf-8") as f:
                    json.dump(structure_meta, f, indent=2, ensure_ascii=False)
                temp_meta.replace(meta_path)
            except Exception as me:
                logger.warning(f"Failed to save markdown structure metadata: {me}")

        return markdown_text

    def _create_chunks(
        self,
        pdf_doc: PDFDocument,
        markdown_text: str,
        doc_id: str,
        doc_type: str,
        revision: Optional[str],
    ) -> List[Dict]:
        """Create chunks from document"""
        # Prepare metadata
        metadata = {
            "doc_type": doc_type,
            "revision": revision,
            "source_format": pdf_doc.source_format,
            "file_name": pdf_doc.file_name,
            "title": pdf_doc.title,
            "author": pdf_doc.author,
        }

        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        # Choose HierarchicalChunker strategy per CLI
        chunker = HierarchicalChunker(
            max_chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            use_token_count=False,  # Use char count for consistency
            chunking_strategy=self.chunk_strategy,
            sentence_window_size=self.sentence_window_size,
        )
        chunks = chunker.chunk_markdown(markdown_text, doc_id, metadata)

        # Convert to dict format
        chunk_dicts = []
        for chunk in chunks:
            chunk_dict = chunk.to_dict()
            # Ensure all metadata is present
            chunk_dict["metadata"].update(metadata)

            # NEW: Enrich with equipment tags using TagNormalizer (additive, safe)
            try:
                from app.rag.normalizers.tag_normalizer import TagNormalizer

                # IMPORTANT: Disable normalization to preserve original tag format (e.g. "04 ZLH 2038A")
                # This ensures tags remain searchable with their original spacing and format
                _tn = TagNormalizer(
                    standardize_separator=False,  # Keep original separators (spaces, hyphens)
                    remove_spaces=False,  # Preserve spaces in tags
                    uppercase=True,  # Still uppercase for consistency
                )
                _tags = _tn.extract_tags(chunk_dict.get("text") or "")
                if _tags:
                    # Use "normalized" (uppercase only) as primary tags
                    normalized_tags = [
                        t.get("normalized") for t in _tags if t.get("normalized")
                    ]
                    raw_tags = [t.get("original") for t in _tags if t.get("original")]
                    if normalized_tags:
                        seen = set()
                        norm_dedup = []
                        for t in normalized_tags:
                            if t not in seen:
                                seen.add(t)
                                norm_dedup.append(t)
                        chunk_dict["metadata"]["tags"] = norm_dedup
                    if raw_tags:
                        preview = []
                        seen_raw = set()
                        for r in raw_tags:
                            r_str = str(r)
                            if r_str not in seen_raw:
                                seen_raw.add(r_str)
                                preview.append(r_str)
                            if len(preview) >= 20:
                                break
                        chunk_dict["metadata"]["tags_raw"] = preview
            except Exception as e:
                # Non-fatal; proceed without tags
                pass

            # Ensure doc_type exists (best-effort heuristic)
            try:
                if "doc_type" not in chunk_dict["metadata"] or not chunk_dict[
                    "metadata"
                ].get("doc_type"):
                    src_hint = f"{chunk_dict['metadata'].get('file_name', '')} {doc_id}"
                    doc_type = None
                    if "Instrument" in src_hint:
                        doc_type = "instrument_list"
                    elif "Manual" in src_hint or "Operating Manual" in src_hint:
                        doc_type = "manual"
                    elif any(k in src_hint.upper() for k in ["P&ID", "P_ID", "PID"]):
                        doc_type = "pid"
                    if doc_type:
                        chunk_dict["metadata"]["doc_type"] = doc_type
            except Exception:
                pass

            chunk_dicts.append(chunk_dict)

        return chunk_dicts

    def _save_chunks(self, chunks: List[Dict], doc_id: str):
        """Save chunks in both JSON and JSONL formats"""
        # Save as JSON (backward compatibility)
        json_file = self.output_dir / "chunks" / f"{doc_id}_chunks.json"
        temp_file = json_file.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        temp_file.replace(json_file)

        # Save as JSONL if enabled
        if self.emit_jsonl:
            jsonl_file = self.output_dir / "chunks" / "chunks.jsonl"

            # Append to JSONL with lock to avoid interleaving lines
            with self._jsonl_lock:
                with open(jsonl_file, "a", encoding="utf-8") as f:
                    for chunk in chunks:
                        f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    def _write_manifests(self, corpus: List[Dict], checksums: List[Dict]):
        """Write manifest files (atomic)"""
        corpus_file = self.output_dir / "manifests" / "corpus.jsonl"
        checksums_file = self.output_dir / "manifests" / "checksums.jsonl"

        # Write corpus manifest
        temp_file = corpus_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            for entry in corpus:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        temp_file.replace(corpus_file)

        # Write checksums manifest
        temp_file = checksums_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            for entry in checksums:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        temp_file.replace(checksums_file)

        logger.info(f"Wrote {len(corpus)} entries to corpus manifest")
        logger.info(f"Wrote {len(checksums)} entries to checksums manifest")

    def _write_doc_id_map(self, doc_id_map: Dict[str, str]):
        """Write doc_id_map.json (atomic)"""
        map_file = self.output_dir / "doc_id_map.json"
        temp_file = map_file.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(doc_id_map, f, indent=2, ensure_ascii=False)

        temp_file.replace(map_file)
        logger.info(f"Wrote {len(doc_id_map)} entries to doc_id_map.json")

    def _write_dedup_report(self):
        """Write deduplication report"""
        if not self.duplicate_groups:
            return

        report_file = self.output_dir / "manifests" / "dedup_report.json"
        temp_file = report_file.with_suffix(".tmp")

        report = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "total_unique": len(self.content_hash_map),
            "total_duplicates": sum(
                len(group) for group in self.duplicate_groups.values()
            ),
            "duplicate_groups": {},
        }

        for content_hash, duplicates in self.duplicate_groups.items():
            representative = self.content_hash_map[content_hash]
            report["duplicate_groups"][content_hash] = {
                "representative": representative["file_path"],
                "duplicates": duplicates,
            }

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        temp_file.replace(report_file)
        logger.info(
            f"Wrote deduplication report with {len(self.duplicate_groups)} groups"
        )

    def _write_table_index(self, table_index: List[Dict]):
        """Write table index file"""
        if not table_index:
            logger.info("No tables found in corpus, skipping table_index.json")
            return

        index_file = self.output_dir / "manifests" / "table_index.json"
        temp_file = index_file.with_suffix(".tmp")

        table_index_data = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "total_tables": len(table_index),
            "tables": table_index,
        }

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(table_index_data, f, indent=2, ensure_ascii=False)

        temp_file.replace(index_file)
        logger.info(f"Wrote table index with {len(table_index)} tables")

    def _extract_table_metadata_from_chunks(
        self, chunks: List[Dict], doc_id: str
    ) -> List[Dict]:
        """Extract table metadata from all chunks of a document"""
        from app.ingestion.table_extractor import extract_table_metadata_from_chunk

        all_table_metadata = []

        for chunk in chunks:
            try:
                # Extract tables from this chunk
                table_metadata_list = extract_table_metadata_from_chunk(chunk)
                if table_metadata_list:
                    all_table_metadata.extend(table_metadata_list)
                    logger.debug(
                        f"Extracted {len(table_metadata_list)} table(s) from chunk {chunk.get('chunk_id')}"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to extract table metadata from chunk {chunk.get('chunk_id')}: {e}"
                )

        if all_table_metadata:
            logger.info(
                f"Extracted {len(all_table_metadata)} table(s) from document {doc_id}"
            )

        return all_table_metadata

    def _write_ingestion_manifest(self) -> Path:
        """Write ingestion manifest for versioning support"""
        manifest_path = self.output_dir / "manifest.json"

        # Calculate total tokens estimate (avg 850 tokens per 1000 chars)
        total_tokens = int(self.stats["total_chunks"] * (self.chunk_size / 1000) * 850)

        # Find chunks artifact
        chunks_jsonl = self.output_dir / "chunks" / "chunks.jsonl"
        artifacts = {}
        if chunks_jsonl.exists():
            artifacts["chunks_jsonl"] = str(
                chunks_jsonl.relative_to(self.output_dir.parent)
            )

        # Create manifest writer
        writer = ManifestWriter(manifest_path)

        # Write manifest
        manifest = writer.write_ingestion_manifest(
            ingestion_id=self.run_id,
            config={
                "source_dir": str(self.source_dir),
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "chunk_strategy": self.chunk_strategy,
                "parser": self.parser,
                "ocr_enabled": self.enable_ocr,
                "ocr_language": self.ocr_language,
                "extract_tables": self.extract_tables,
                "table_min_rows": self.table_min_rows,
                "table_min_cols": self.table_min_cols,
            },
            source_stats={
                "data_dir": str(self.source_dir),
                "total_files": self.stats["total_pdfs"],
                "processed_files": self.stats["processed"],
                "quarantined_files": self.stats["quarantine_count"],
            },
            chunk_stats={
                "total_chunks": self.stats["total_chunks"],
                "unique_chunks": self.stats[
                    "total_chunks"
                ],  # Assuming all unique for now
                "duplicate_chunks": 0,
                "avg_tokens_per_chunk": total_tokens
                // max(1, self.stats["total_chunks"]),
            },
            embedding_stats={
                "total_embedded": 0,  # Will be filled by embedding phase
                "cache_hits": 0,
                "api_calls": 0,
                "total_cost_usd": 0.0,
            },
            artifacts=artifacts,
        )

        logger.info(f"Wrote ingestion manifest: {manifest_path}")
        return manifest_path

    def _create_version_snapshot(self, manifest_path: Path):
        """Create version snapshot after successful ingestion"""
        try:
            # Auto-generate version ID if not provided
            if not self.version_id:
                self.version_id = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Initialize version manager
            base_dir = (
                self.output_dir.parent
                if self.output_dir.name.startswith("ingestion")
                else self.output_dir.parent.parent
            )
            vm = VersionManager(base_dir)

            # Create version
            version_meta = vm.create_version(
                version_id=self.version_id,
                ingestion_manifest_path=manifest_path,
                index_manifest_path=None,
                description=self.version_description
                or f"Ingestion: {self.stats['processed']} docs, {self.stats['total_chunks']} chunks",
                tags=self.version_tags,
            )

            logger.info("")
            logger.info("🎉 " + "=" * 76)
            logger.info(f"✅ VERSION SNAPSHOT CREATED: {version_meta['version_id']}")
            logger.info("=" * 80)
            logger.info(f"Created at: {version_meta['created_at']}")
            logger.info(f"Total chunks: {version_meta['stats']['total_chunks']}")
            logger.info(f"Version directory: {base_dir / 'versions' / self.version_id}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Failed to create version snapshot: {e}", exc_info=True)
            logger.warning(
                "Ingestion completed successfully, but version creation failed"
            )
            logger.info(f"You can manually create a version using:")
            logger.info(
                f"  python tools/ops/create_version.py --ingestion-dir {self.output_dir} --version-id {self.version_id or 'v1.0'}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Ingest PDF documents with deduplication and quarantine support"
    )

    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Directory containing PDF files to process",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/ingestion"),
        help="Directory for output files (default: artifacts/ingestion)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker threads (default: auto, max 4)",
    )

    parser.add_argument(
        "--enable-ocr", action="store_true", help="Enable OCR for scanned pages"
    )

    parser.add_argument(
        "--ocr-lang",
        type=str,
        default="vie+eng",
        help="Language for OCR (default: vie+eng for Vietnamese & English)",
    )

    parser.add_argument(
        "--parser",
        type=str,
        choices=["auto", "pymupdf", "unstructured"],
        default="auto",
        help="PDF parser to use (default: auto)",
    )

    parser.add_argument(
        "--emit-jsonl",
        action="store_true",
        default=True,
        help="Emit JSONL outputs in addition to JSON (default: True)",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Target chunk size in characters (default: 1000)",
    )

    parser.add_argument(
        "--chunk-strategy",
        type=str,
        choices=["hierarchical", "sentence-window", "small-to-big"],
        default="hierarchical",
        help="Chunking strategy to use (default: hierarchical)",
    )

    parser.add_argument(
        "--sentence-window-size",
        type=int,
        default=5,
        help="Number of sentences per window for sentence-window chunking (default: 5)",
    )

    parser.add_argument(
        "--use-llm-classifier",
        action="store_true",
        help="Use LLM for document classification when rules fail (requires local LLM)",
    )

    parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help="Local LLM model name for classification (e.g., 'llama2', 'mistral')",
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Overlap between chunks in characters (default: 200)",
    )

    parser.add_argument(
        "--extract-tables",
        action="store_true",
        default=True,
        help="Enable table extraction from PDFs (default: True)",
    )

    parser.add_argument(
        "--no-extract-tables",
        action="store_false",
        dest="extract_tables",
        help="Disable table extraction",
    )

    parser.add_argument(
        "--table-min-rows",
        type=int,
        default=2,
        help="Minimum rows for valid table (default: 2)",
    )

    parser.add_argument(
        "--table-min-cols",
        type=int,
        default=2,
        help="Minimum columns for valid table (default: 2)",
    )

    parser.add_argument(
        "--create-version",
        action="store_true",
        help="Automatically create version snapshot after successful ingestion",
    )

    parser.add_argument(
        "--version-id",
        type=str,
        default=None,
        help="Version identifier (default: auto-generated timestamp)",
    )

    parser.add_argument(
        "--version-description",
        type=str,
        default="",
        help="Human-readable version description",
    )

    parser.add_argument(
        "--version-tags",
        type=str,
        nargs="+",
        default=None,
        help="Optional tags for version categorization (e.g., production stable)",
    )

    parser.add_argument(
        "--enable-pid-tags",
        action="store_true",
        help="Enable P&ID tag extraction for CAD-like documents (requires ENABLE_PID_TAGS=true in .env)",
    )

    args = parser.parse_args()

    # Validate source directory
    if not args.source_dir.exists():
        logger.error(f"Source directory does not exist: {args.source_dir}")
        sys.exit(1)

    # Check OCR availability if requested (PaddleOCR)
    if args.enable_ocr:
        from app.ingestion.paddle_ocr_config import get_ocr_status as get_paddle_status

        ocr_status = get_paddle_status()
        if not ocr_status["ocr_enabled"]:
            logger.warning(
                "OCR requested but PaddleOCR is not available. Continuing without OCR..."
            )
            args.enable_ocr = False
        else:
            engine = ocr_status.get("ocr_engine", "PaddleOCR")
            gpu = ocr_status.get("gpu_available", False)
            logger.info(f"OCR enabled using {engine} (GPU: {gpu})")

    # Check for unstructured.io if requested
    if args.parser == "unstructured":
        try:
            import unstructured

            logger.info("Unstructured.io parser available")
        except ImportError:
            logger.warning("Unstructured.io not installed, falling back to PyMuPDF")
            args.parser = "pymupdf"

    # Initialize and run pipeline
    pipeline = IngestionPipeline(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        workers=args.workers,
        enable_ocr=args.enable_ocr,
        ocr_language=args.ocr_lang,
        parser=args.parser,
        emit_jsonl=args.emit_jsonl,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        chunk_strategy=args.chunk_strategy,
        sentence_window_size=args.sentence_window_size,
        use_llm_classifier=args.use_llm_classifier,
        llm_model=args.llm_model,
        extract_tables=args.extract_tables,
        table_min_rows=args.table_min_rows,
        table_min_cols=args.table_min_cols,
        create_version=args.create_version,
        version_id=args.version_id,
        version_description=args.version_description,
        version_tags=args.version_tags,
        enable_pid_tags=args.enable_pid_tags,
    )

    stats = pipeline.run()

    # Exit with appropriate code
    # Note: quarantined files (e.g., drawings without text) are expected and not errors
    if stats["failed"] > 0:
        logger.error(f"Ingestion completed with {stats['failed']} failures")
        sys.exit(1)

    if stats["quarantine_count"] > 0:
        logger.warning(
            f"Note: {stats['quarantine_count']} files quarantined (likely drawings without text)"
        )

    logger.info("✅ Ingestion completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
