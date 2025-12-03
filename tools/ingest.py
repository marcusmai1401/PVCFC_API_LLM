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

# Fix for "maximum recursion depth exceeded" errors with complex PDFs
# Some PDFs with deeply nested structures (tables, annotations) require higher limit
# PRODUCTION HOTFIX: Increased to 50000 for complex CAD drawings (>10k vector layers)
# Safe for Windows with 24GB RAM. Handles most technical drawings without crash.
sys.setrecursionlimit(50000)  # Default is 1000, previous: 10000

from loguru import logger

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    env_path = Path(PROJECT_ROOT) / ".env"
    if env_path.exists():
        # Use override=True to ensure .env values override existing env vars
        load_dotenv(env_path, override=True)
        logger.info(f"Loaded environment variables from {env_path}")

        # Explicitly set GOOGLE_APPLICATION_CREDENTIALS if in .env
        import os

        if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
            # Try to read from .env file directly
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GOOGLE_APPLICATION_CREDENTIALS="):
                        creds_path = line.split("=", 1)[1].strip().strip('"').strip("'")
                        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
                        logger.info(
                            f"Set GOOGLE_APPLICATION_CREDENTIALS from .env: {creds_path}"
                        )
                        break

        # Verify credentials file exists
        creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds and Path(creds).exists():
            logger.info(f"Verified Google Cloud credentials: {creds}")
        elif creds:
            logger.warning(f"Google Cloud credentials file not found: {creds}")

        # Force reload config singleton to pick up new env vars
        import app.config.pipeline_config as config_module

        config_module._config_instance = None
        logger.info("Reset config singleton to reload with new environment variables")
except ImportError:
    logger.warning(
        "python-dotenv not installed, using system environment variables only"
    )

# NOTE: Using CADLikeGate for CAD-like document classification
from app.ingestion.cadlike_gate import get_cadlike_gate

# NOTE: PaddleOCR is deprecated in favor of Google Cloud Vision API
# from app.ingestion.paddle_ocr_config import get_ocr_status
from app.ingestion.pdf_processor import PageContent, PDFDocument, PDFProcessor

# Classification Pipeline for 4-category taxonomy (v2.0)
try:
    from app.classification.pipeline import (
        ClassificationPipeline,
        get_classification_pipeline,
        PipelineResult,
    )
    from app.classification.classifier import ClassificationResult
    CLASSIFICATION_AVAILABLE = True
except ImportError:
    CLASSIFICATION_AVAILABLE = False
    logger.warning("Classification pipeline not available")
from app.rag.chunkers.hierarchical_chunker import HierarchicalChunker
from app.storage.manifest_writer import ManifestWriter
from app.storage.version_manager import VersionManager

# P&ID tag extraction (optional)
try:
    from app.ingestion.tags.orchestrator import TagExtractionOrchestrator
    from app.rag.spatial.component_extractor import SpatialComponentExtractor
    from app.rag.spatial.component_indexer import SpatialComponentIndexer

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
        enable_classification: bool = True,  # NEW: Enable 4-category classification
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

        # Default workers optimized for single GPU (Real-ESRGAN contention)
        # With GPU operations (Real-ESRGAN), more workers cause contention
        # Test results: 2 workers optimal for RTX 4060 (single GPU)
        if workers is None:
            workers = 2  # Reduced from 4 to avoid GPU contention
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

        # Classification settings (4-category taxonomy)
        self.enable_classification = enable_classification and CLASSIFICATION_AVAILABLE

        # Initialize CADLikeGate for document classification
        self._cadlike_gate = get_cadlike_gate()
        
        # Initialize Classification Pipeline (if enabled)
        self._classification_pipeline = None
        if self.enable_classification:
            try:
                self._classification_pipeline = get_classification_pipeline(
                    use_cadlike_gate=True,
                    cad_score_threshold=0.55
                )
                logger.info("✅ Classification pipeline enabled (4-category taxonomy)")
            except Exception as e:
                logger.warning(f"Failed to initialize classification pipeline: {e}")
                self.enable_classification = False

        # Initialize P&ID tag extraction orchestrator (if enabled)
        self.tag_orchestrator = None
        self.component_extractor = None
        self.component_indexer = None
        if self.enable_pid_tags:
            try:
                # PATCH: Sync TagExtractionOrchestrator paths with pipeline output_dir
                # This ensures tags are written to {output_dir}/entities instead of default artifacts
                import os

                # Path is already imported globally
                import app.config.pipeline_config as config_module

                # Set env vars to override config defaults
                os.environ["ENTITIES_DIR"] = str(self.output_dir / "entities")
                os.environ["LAYOUT_DIR"] = str(self.output_dir / "page_layout")
                os.environ["CROPS_DIR"] = str(self.output_dir / "crops")
                os.environ["LOGS_DIR"] = str(self.output_dir / "logs")

                # Force reload config singleton to pick up new paths
                config_module._config_instance = None
                logger.info(f"Synced P&ID tag paths to: {self.output_dir}")

                self.tag_orchestrator = TagExtractionOrchestrator(
                    enable_crops=True,
                    lazy_crops=True,  # Don't generate crops during ingestion for speed
                )
                # Initialize component extraction for Level 2 spatial search
                self.component_extractor = SpatialComponentExtractor()
                self.component_indexer = SpatialComponentIndexer()
                logger.info(
                    "✅ P&ID tag extraction enabled (with component extraction for Level 2)"
                )
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
            # Classification stats (4-category taxonomy)
            "classification_count": 0,  # Documents classified
            "classification_guardrail_triggered": 0,  # P&ID guardrail triggers
            "classification_needs_review": 0,  # Low confidence classifications
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
            self.output_dir / "entities",  # NEW: For tags.jsonl
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _cleanup_jsonl_files(self):
        """
        Clean up JSONL files from previous runs to prevent duplicates.
        Called at the start of each ingestion run.

        This method backs up and clears chunks.jsonl and tags.jsonl to ensure
        that each run starts with a clean slate and doesn't accumulate duplicates
        from previous runs.

        Note: tags.jsonl is only cleaned if P&ID tag extraction is enabled,
        to preserve existing tags when running ingestion without P&ID processing.
        """
        # Always cleanup chunks.jsonl
        jsonl_files_to_clean = [
            self.output_dir / "chunks" / "chunks.jsonl",
        ]

        # Only cleanup tags.jsonl if tag extraction is enabled
        # This prevents losing existing tags when running ingestion without P&ID processing
        if self.enable_pid_tags:
            jsonl_files_to_clean.append(self.output_dir / "entities" / "tags.jsonl")
            logger.info("P&ID tag extraction enabled - will cleanup tags.jsonl")
        else:
            logger.info("P&ID tag extraction disabled - preserving existing tags.jsonl")

        for jsonl_file in jsonl_files_to_clean:
            if jsonl_file.exists():
                # Create backup before deletion
                backup_file = jsonl_file.with_suffix(".jsonl.backup")
                if backup_file.exists():
                    backup_file.unlink()  # Remove old backup

                shutil.copy2(jsonl_file, backup_file)
                logger.info(f"✅ Backed up {jsonl_file.name} to {backup_file.name}")

                # Clear the file
                jsonl_file.unlink()
                logger.info(f"🧹 Cleaned up {jsonl_file.name} from previous run")

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
        logger.info(f"Classification: {self.enable_classification} (4-category taxonomy)")
        logger.info(f"Run ID: {self.run_id}")
        logger.info("=" * 80)

        self.stats["start_time"] = datetime.now()

        # Ensure output directories exist
        self._setup_output_dirs()

        # NEW: Clean up JSONL files from previous runs to prevent duplicates
        self._cleanup_jsonl_files()

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
        
        # Classification stats (4-category taxonomy)
        if self.enable_classification:
            logger.info(f"Documents classified: {self.stats['classification_count']}")
            logger.info(f"P&ID guardrail triggered: {self.stats['classification_guardrail_triggered']}")
            logger.info(f"Needs review: {self.stats['classification_needs_review']}")

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
        normalized = self._normalize_text(text)
        # Calculate SHA1 hash
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison
        Used by both content hashing and similarity calculation
        """
        import re

        # Unicode normalization
        normalized = unicodedata.normalize("NFKC", text)

        # Lowercase
        normalized = normalized.lower()

        # Remove line-ending hyphens before collapsing whitespace
        normalized = normalized.replace("-\n", "").replace("-\r\n", "")

        # Collapse all whitespace (including newlines) to single spaces
        normalized = re.sub(r"\s+", " ", normalized)

        # Strip leading/trailing whitespace
        normalized = normalized.strip()

        return normalized

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using character-level comparison
        Returns value between 0.0 (completely different) and 1.0 (identical)

        Uses simple character overlap ratio for speed:
        similarity = 2 * len(common_chars) / (len(text1) + len(text2))
        """
        if not text1 or not text2:
            return 0.0

        # Use set intersection for fast approximate similarity
        # This is faster than difflib but less accurate
        # Good enough for high-threshold deduplication (≥98%)

        # Split into words for better granularity than characters
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        # Jaccard similarity: intersection / union
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

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

    def _rasterize_pdf(
        self, pdf_path: Path, output_path: Path, dpi: int = 200, jpeg_quality: int = 85
    ) -> bool:
        """
        Rasterize PDF to image-only PDF to eliminate complex vector structures.
        This removes recursion risks from deeply nested PDF objects.

        Args:
            pdf_path: Original PDF path
            output_path: Output path for rasterized PDF
            dpi: Rendering DPI (180-216 recommended for OCR balance)
            jpeg_quality: JPEG compression quality (80-85 for size/quality balance)

        Returns:
            True if successful, False otherwise
        """
        try:
            import fitz  # PyMuPDF

            logger.info(f"🔄 Rasterizing PDF to eliminate recursion: {pdf_path.name}")
            logger.info(f"   DPI: {dpi}, JPEG quality: {jpeg_quality}")

            # Open original PDF
            src_doc = fitz.open(str(pdf_path))

            # Create new PDF document for rasterized pages
            dst_doc = fitz.open()  # New empty PDF

            # Process each page
            for page_num in range(len(src_doc)):
                page = src_doc[page_num]

                # Render page to image (pixmap)
                zoom = dpi / 72.0  # Convert DPI to zoom factor
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # Convert pixmap to JPEG bytes for compression
                import io

                from PIL import Image

                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Compress as JPEG
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="JPEG", quality=jpeg_quality, optimize=True)
                img_data = img_bytes.getvalue()

                # Create new page with image
                # Use original page size
                page_rect = page.rect
                new_page = dst_doc.new_page(
                    width=page_rect.width, height=page_rect.height
                )

                # Insert image to fill entire page
                new_page.insert_image(page_rect, stream=img_data, keep_proportion=True)

                logger.debug(
                    f"   Rasterized page {page_num + 1}/{len(src_doc)}: "
                    f"{pix.width}x{pix.height}px, {len(img_data)//1024}KB"
                )

            # Save rasterized PDF
            dst_doc.save(str(output_path), garbage=4, deflate=True)
            dst_doc.close()
            src_doc.close()

            # Verify output file exists and has reasonable size
            if output_path.exists():
                output_size_mb = output_path.stat().st_size / (1024 * 1024)
                logger.info(
                    f"✅ Rasterized PDF created: {output_path.name} ({output_size_mb:.2f} MB)"
                )
                return True
            else:
                logger.error(f"❌ Rasterized PDF not created: {output_path}")
                return False

        except Exception as e:
            logger.error(f"❌ Rasterization failed for {pdf_path.name}: {e}")
            logger.exception(e)
            return False

    def _process_single_pdf(self, pdf_path: Path) -> Optional[Dict]:
        """
        Process a single PDF with deduplication check and auto-fallback for recursion errors.

        Strategy:
        1. Try normal processing (vector + OCR)
        2. If RecursionError → Fallback to rasterized PDF (image-only) + OCR

        Returns:
            Dict with status and data
        """
        try:
            # Calculate file hash
            file_hash = self._calculate_file_hash(pdf_path)
            file_size = pdf_path.stat().st_size
            mtime = pdf_path.stat().st_mtime

            # ===== FILE HASH DEDUPLICATION - DISABLED =====
            # DISABLED: Process all files including exact duplicates
            # Original code commented out to allow duplicate file processing
            # with self._dedup_lock:
            #     if file_hash in self.file_hash_seen:
            #         self.stats["duplicates_skipped"] += 1
            #         logger.info(
            #             f"Skipping exact duplicate (file_hash): {pdf_path.name}"
            #         )
            #         return {"status": "skipped", "reason": "exact_file_duplicate"}
            #     self.file_hash_seen.add(file_hash)
            # ===== END FILE HASH DEDUPLICATION =====

            # Classify document type BEFORE processing (for OCR threshold determination)
            gate_decision = self._cadlike_gate.evaluate(pdf_path)
            is_cad_like = gate_decision.is_cadlike

            # Set document type based on CADLikeGate decision
            document_type = "CAD-like" if is_cad_like else "non-CAD-like"

            logger.debug(
                f"CADLikeGate: {pdf_path.name} -> {document_type} "
                f"(score={gate_decision.score:.3f}, method={gate_decision.detection_method})"
            )

            # === PHASE 1: Try normal processing ===
            # Wrap ALL processing in RecursionError handler to catch errors at any stage
            pdf_doc = None
            used_ocr = False
            processing_mode = "normal"  # Track processing mode for manifest
            fallback_reason = None
            actual_pdf_path = pdf_path  # May change if rasterized
            full_text = None  # Initialize early
            doc_id = None
            markdown_text = None
            chunks = None

            try:
                # === Try normal processing (all steps) ===
                # Single processing with OCR enabled
                # Per-page OCR decisions controlled by thresholds in PDFProcessor
                processor = PDFProcessor(
                    enable_ocr=True,  # Always enabled
                    extract_tables=self.extract_tables,
                    table_min_rows=self.table_min_rows,
                    table_min_cols=self.table_min_cols,
                    document_type=document_type,
                )
                pdf_doc = processor.process_pdf(pdf_path)

                # Check if OCR was actually used on any page
                used_ocr = pdf_doc.source_format in {"scan", "mixed"}

                # === CRITICAL: Also process full text extraction inside RecursionError handler ===
                # RecursionError can occur during text extraction, not just PDF parsing
                full_text = "\n".join(page.text for page in pdf_doc.pages)

                # Check if text was extracted
                if not full_text.strip():
                    # No text could be extracted even with OCR
                    self._add_to_quarantine(pdf_path, "ocr_failed", "No text extracted")
                    return {"status": "quarantine", "reason": "ocr_failed"}

                # Calculate content hash
                content_hash = self._calculate_content_hash(full_text)

                # Generate doc_id
                doc_id = self._generate_doc_id(pdf_path, pdf_doc)

                # Detect document type and revision (CAD-like vs non-CAD-like)
                doc_type, revision = self._classify_document(pdf_path, pdf_doc)
                
                # === 4-CATEGORY CLASSIFICATION (v2.0) ===
                # Run classification pipeline for taxonomy-based classification
                classification_result = None
                if self.enable_classification and self._classification_pipeline:
                    classification_result = self._run_classification(pdf_path, doc_id)

                # Save processed document
                self._save_processed_document(pdf_doc, doc_id)

                # Convert to markdown
                markdown_text = self._convert_to_markdown(pdf_doc, doc_id)

                # Create chunks (with classification metadata)
                chunks = self._create_chunks(
                    pdf_doc,
                    markdown_text,
                    doc_id,
                    doc_type,
                    revision,
                    self.chunk_strategy,
                    classification_result,
                )

            except RecursionError as e:
                # === PHASE 2: Fallback to rasterized processing ===
                logger.warning(
                    f"RecursionError in normal mode for {pdf_path.name}, "
                    f"attempting fallback to rasterized PDF..."
                )
                fallback_reason = f"RecursionError: {str(e)[:100]}"

                # RESOURCE LEAK FIX: Use try...finally to GUARANTEE temp file cleanup
                # Initialize path before try block so finally can always access it
                rasterized_path = None
                fallback_result = None  # Track early returns

                try:
                    # Create temp rasterized PDF
                    temp_dir = self.output_dir / "temp_rasterized"
                    temp_dir.mkdir(parents=True, exist_ok=True)

                    rasterized_path = temp_dir / f"rasterized_{pdf_path.stem}.pdf"

                    # Rasterize PDF
                    raster_success = self._rasterize_pdf(
                        pdf_path=pdf_path,
                        output_path=rasterized_path,
                        dpi=200,  # Good balance for OCR
                        jpeg_quality=85,  # High quality but compressed
                    )

                    if not raster_success:
                        logger.error(f"Rasterization failed for {pdf_path.name}")
                        self._add_to_quarantine(
                            pdf_path,
                            "recursion_error",
                            f"RecursionError in normal mode, rasterization also failed: {e}",
                        )
                        fallback_result = {
                            "status": "quarantine",
                            "reason": "recursion_error_raster_failed",
                        }
                        return fallback_result

                    logger.info(f"Retrying with rasterized PDF (safe mode)...")

                    # Use safe configuration:
                    # - No table extraction (rasterized PDF has no table structure)
                    # - Force OCR (rasterized = image-only)
                    # - Same chunking strategy as normal mode (preserve page metadata)
                    processor_safe = PDFProcessor(
                        enable_ocr=True,
                        extract_tables=False,  # No tables in rasterized PDF
                        document_type=document_type,
                    )
                    pdf_doc = processor_safe.process_pdf(rasterized_path)

                    # Extract full text (may also trigger RecursionError)
                    full_text = "\n".join(page.text for page in pdf_doc.pages)

                    # Check if text was extracted
                    if not full_text.strip():
                        self._add_to_quarantine(
                            pdf_path,
                            "ocr_failed",
                            "No text extracted from rasterized PDF",
                        )
                        fallback_result = {
                            "status": "quarantine",
                            "reason": "ocr_failed",
                        }
                        return fallback_result

                    # Mark as rasterized processing
                    processing_mode = "rasterized-ocr"
                    used_ocr = True  # Rasterized always uses OCR
                    actual_pdf_path = rasterized_path

                    # Calculate content hash
                    content_hash = self._calculate_content_hash(full_text)

                    # Generate doc_id
                    doc_id = self._generate_doc_id(pdf_path, pdf_doc)

                    # Detect document type and revision (CAD-like vs non-CAD-like)
                    doc_type, revision = self._classify_document(pdf_path, pdf_doc)
                    
                    # === 4-CATEGORY CLASSIFICATION (v2.0) ===
                    # Run classification pipeline for taxonomy-based classification
                    # Note: Use original pdf_path for classification, not rasterized
                    classification_result = None
                    if self.enable_classification and self._classification_pipeline:
                        classification_result = self._run_classification(pdf_path, doc_id)

                    # Save processed document
                    self._save_processed_document(pdf_doc, doc_id)

                    # Convert to markdown
                    markdown_text = self._convert_to_markdown(pdf_doc, doc_id)

                    # --- PRODUCTION SAFEGUARD: Triple Safety Net Chunking ---
                    # Try hierarchical first (preserves metadata), fallback to sentence-window if needed
                    try:
                        # Priority 1: Use configured strategy (usually hierarchical) for best metadata
                        # With limit 50k, most files will succeed at this step
                        chunks = self._create_chunks(
                            pdf_doc,
                            markdown_text,
                            doc_id,
                            doc_type,
                            revision,
                            self.chunk_strategy,
                            classification_result,
                        )
                    except RecursionError:
                        # Priority 2: FINAL SAFETY NET - Downgrade to flat chunking
                        # If file exceeds 50k layers (extremely rare), accept strategy downgrade
                        # 'sentence-window' uses no recursion -> GUARANTEES NO CRASH
                        logger.warning(
                            f"RecursionError during fallback chunking (>50k layers). "
                            f"Downgrading to 'sentence-window' strategy to save ingestion: {pdf_path.name}"
                        )
                        chunks = self._create_chunks(
                            pdf_doc,
                            markdown_text,
                            doc_id,
                            doc_type,
                            revision,
                            "sentence-window",
                            classification_result,
                        )
                    # ---------------------------------------------------------------

                    logger.success(
                        f"Fallback successful: {pdf_path.name} processed via rasterization "
                        f"({len(pdf_doc.pages)} pages)"
                    )

                except RecursionError as e_raster:
                    # Still recursion error even after rasterization (or during rasterization)
                    logger.error(
                        f"RecursionError in fallback processing: {pdf_path.name}"
                    )
                    self._add_to_quarantine(
                        pdf_path,
                        "recursion_error",
                        f"RecursionError in fallback (rasterization or processing): {e_raster}",
                    )
                    fallback_result = {
                        "status": "quarantine",
                        "reason": "recursion_error_persistent",
                    }
                    return fallback_result

                except Exception as e_fallback:
                    logger.error(
                        f"Fallback processing failed: {pdf_path.name} - {e_fallback}"
                    )
                    self._add_to_quarantine(
                        pdf_path,
                        "read_error",
                        f"Normal mode: RecursionError, Fallback mode: {e_fallback}",
                    )
                    fallback_result = {
                        "status": "quarantine",
                        "reason": "rasterized_processing_failed",
                    }
                    return fallback_result

                finally:
                    # GUARANTEED CLEANUP: This block ALWAYS runs, even if return/exception above
                    # Only cleanup if we're NOT going to use the file in subsequent processing
                    # (i.e., if we had an error or early return)
                    if fallback_result is not None and rasterized_path is not None:
                        try:
                            if rasterized_path.exists():
                                rasterized_path.unlink()
                                logger.debug(
                                    f"Cleaned up temp rasterized PDF (in finally): {rasterized_path.name}"
                                )
                        except Exception as cleanup_err:
                            logger.warning(
                                f"Failed to cleanup temp PDF in finally: {cleanup_err}"
                            )

            except Exception as e:
                # CRITICAL: Only catch non-RecursionError exceptions here
                # RecursionError must be handled by the specific handler above
                if isinstance(e, RecursionError):
                    # This should NEVER happen - RecursionError should be caught above
                    # But if it does, log it as critical error
                    logger.critical(
                        f"❌ CRITICAL: RecursionError leaked to general exception handler: {pdf_path.name}"
                    )
                    logger.critical(
                        f"This indicates a bug in exception handling logic!"
                    )
                    self._add_to_quarantine(
                        pdf_path, "recursion_error_bug", f"Leaked RecursionError: {e}"
                    )
                    return {"status": "quarantine", "reason": "recursion_error_bug"}
                # Document is corrupted or unreadable (non-recursion error)
                logger.error(f"❌ Error processing {pdf_path.name}: {e}")
                self._add_to_quarantine(pdf_path, "read_error", str(e))
                return {"status": "quarantine", "reason": "read_error"}

            # === All processing completed successfully (normal or fallback mode) ===
            # doc_id, doc_type, revision, markdown_text, chunks, content_hash already set above

            # RESOURCE LEAK FIX: Wrap entire success path in try...finally
            # to GUARANTEE temp file cleanup even if exceptions occur during
            # _save_chunks, P&ID extraction, spatial extraction, etc.
            try:
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

                # === SPATIAL COMPONENT EXTRACTION (Level 2) ===
                # Extract individual components for spatial proximity search
                # Strategy: Extract for ALL pages if document is CAD-like (not just taggy pages)
                # This ensures 100% coverage for tags that Tag Extraction might miss
                # DISABLED for rasterized mode (no vector structure available)
                if (
                    self.enable_pid_tags
                    and self.component_extractor
                    and self.component_indexer
                    and doc_type == "CAD-like"
                    and processing_mode
                    != "rasterized-ocr"  # Skip spatial extraction for rasterized files
                ):
                    try:
                        logger.debug(
                            f"Extracting spatial components for CAD-like document: {pdf_path.name}"
                        )

                        # Get config for layout directory
                        from app.config import get_config

                        config = get_config()
                        layout_dir = Path(config.LAYOUT_DIR)

                        all_components = []

                        # NEW: Process ALL pages for CAD-like documents (not just taggy pages)
                        # This ensures we don't miss tags on pages where Tag Extraction failed
                        all_pages = list(range(1, pdf_doc.num_pages + 1))

                        logger.info(
                            f"Processing ALL {len(all_pages)} pages for spatial components "
                            f"(CAD-like document, ensuring 100% coverage)"
                        )

                        for page_num in all_pages:
                            # Check if layout file exists (Tag Extraction may have saved it)
                            layout_file = layout_dir / f"page_{doc_id}_{page_num}.json"

                            if layout_file.exists():
                                # Layout already exists (from Tag Extraction), load and use it
                                try:
                                    # Load layout JSON
                                    with open(layout_file, "r", encoding="utf-8") as f:
                                        layout_data = json.load(f)

                                    # Reconstruct PageLayout object
                                    from app.ingestion.layout.page_layout_builder import (
                                        PageLayout,
                                        TextSpan,
                                        VectorDrawing,
                                    )

                                    # Reconstruct spans
                                    spans = [
                                        TextSpan(
                                            text=s["text"],
                                            bbox=s["bbox"],
                                            font_size=s["font_size"],
                                            rotation_deg=s["rotation_deg"],
                                            span_id=s["span_id"],
                                        )
                                        for s in layout_data.get("spans", [])
                                    ]

                                    # Reconstruct drawings
                                    drawings = [
                                        VectorDrawing(
                                            type=d["type"],
                                            coords=d["coords"],
                                            color=d.get("color"),
                                            thickness=d.get("thickness"),
                                        )
                                        for d in layout_data.get("drawings", [])
                                    ]

                                    # Create PageLayout
                                    layout = PageLayout(
                                        doc_id=layout_data["doc_id"],
                                        page=layout_data["page"],
                                        page_width=layout_data["page_width"],
                                        page_height=layout_data["page_height"],
                                        spans=spans,
                                        drawings=drawings,
                                        is_raster=layout_data.get("is_raster", False),
                                        ocr_confidence=layout_data.get(
                                            "ocr_confidence"
                                        ),
                                    )

                                    logger.debug(
                                        f"Loaded existing layout for page {page_num}"
                                    )

                                except Exception as e:
                                    logger.warning(
                                        f"Failed to load existing layout for page {page_num}: {e}, building new layout"
                                    )
                                    # Build layout from scratch if loading fails
                                    layout = self._build_layout_for_page(
                                        pdf_path, page_num, doc_id
                                    )
                            else:
                                # Layout doesn't exist (page not processed by Tag Extraction)
                                # Build layout from scratch for spatial indexing
                                logger.debug(
                                    f"Layout not found for page {page_num}, building for spatial indexing"
                                )
                                layout = self._build_layout_for_page(
                                    pdf_path, page_num, doc_id
                                )

                            # Extract components from layout
                            if layout:
                                try:
                                    components = (
                                        self.component_extractor.extract_components(
                                            layout
                                        )
                                    )
                                    all_components.extend(components)
                                    logger.debug(
                                        f"Extracted {len(components)} components from page {page_num}"
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to extract components from page {page_num}: {e}"
                                    )

                        # Bulk index components
                        if all_components:
                            indexed_count = self.component_indexer.index_components(
                                all_components
                            )
                            logger.info(
                                f"Indexed {indexed_count} spatial components for {doc_id} "
                                f"({len(taggy_pages)} taggy pages)"
                            )

                            # Update stats (thread-safe)
                            with self._stats_lock:
                                if "spatial_components_indexed" not in self.stats:
                                    self.stats["spatial_components_indexed"] = 0
                                self.stats[
                                    "spatial_components_indexed"
                                ] += indexed_count
                        else:
                            logger.debug(
                                f"No components extracted from {pdf_path.name}"
                            )

                    except Exception as e:
                        # Don't crash main pipeline on component extraction errors
                        logger.warning(
                            f"Spatial component extraction failed for {pdf_path.name}: {e}"
                        )
                        logger.debug(f"Component extraction error:", exc_info=True)
                # === END SPATIAL COMPONENT EXTRACTION ===

                # Extract table metadata from chunks
                table_metadata = self._extract_table_metadata_from_chunks(
                    chunks, doc_id
                )

                # Count pages by source_format
                scanned_count = (
                    pdf_doc.num_pages if pdf_doc.source_format == "scan" else 0
                )
                vector_count = (
                    pdf_doc.num_pages if pdf_doc.source_format == "vector" else 0
                )

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
                    "processing_mode": processing_mode,  # Track if fallback was used
                }

                # Add fallback metadata if applicable
                if fallback_reason:
                    corpus_entry["fallback_reason"] = fallback_reason
                    corpus_entry["original_file_path"] = str(pdf_path)
                
                # Add classification metadata (4-category taxonomy)
                if classification_result:
                    corpus_entry["category"] = classification_result.get("category")
                    corpus_entry["classification_doc_type"] = classification_result.get("doc_type")
                    corpus_entry["classification_status"] = classification_result.get("status")
                    corpus_entry["classification_confidence"] = classification_result.get("confidence")
                    corpus_entry["classification_method"] = classification_result.get("method")

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

            finally:
                # GUARANTEED CLEANUP: This block ALWAYS runs, even if exception occurs
                # during _save_chunks, P&ID extraction, spatial extraction, etc.
                if processing_mode == "rasterized-ocr" and actual_pdf_path != pdf_path:
                    try:
                        if actual_pdf_path.exists():
                            actual_pdf_path.unlink()
                            logger.debug(
                                f"Cleaned up temp rasterized PDF (finally block): {actual_pdf_path.name}"
                            )
                    except Exception as cleanup_err:
                        logger.warning(
                            f"Failed to cleanup temp PDF in finally: {cleanup_err}"
                        )

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
        Classify document type (simplified to CAD-like vs non-CAD-like)

        NOTE: Previously used DocumentClassifier with 15+ types.
        Now simplified to binary classification using CADLikeGate results.

        Returns:
            Tuple of (doc_type, revision) where doc_type is 'CAD-like' or 'non-CAD-like'
        """
        # Use CADLikeGate evaluation result (already computed in _process_single_pdf)
        gate_decision = self._cadlike_gate.evaluate(pdf_path)
        doc_type = "CAD-like" if gate_decision.is_cadlike else "non-CAD-like"

        # Extract revision from filename (simple pattern matching)
        revision = self._extract_revision_from_filename(pdf_path.name)

        return doc_type, revision

    def _extract_revision_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract revision code from filename (e.g., Rev A, Rev.B, R01, etc.)

        Returns:
            Revision string or None
        """
        import re

        # Common revision patterns
        patterns = [
            r"Rev[\s._-]*([A-Z0-9]+)",  # Rev A, Rev.B, Rev_C
            r"R([0-9]{2,3})",  # R01, R02
            r"V([0-9]+)",  # V1, V2
            r"_([A-Z])\.",  # _A., _B.
        ]

        filename_upper = filename.upper()

        for pattern in patterns:
            match = re.search(pattern, filename_upper, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _run_classification(
        self, pdf_path: Path, doc_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Run 4-category classification pipeline on a PDF document.
        
        This method integrates the ClassificationPipeline to classify documents
        into the 4-category taxonomy (ENGINEERING_DESIGN, VENDOR_EQUIPMENT,
        OPERATIONS_MAINTENANCE, SAFETY_MANAGEMENT, or UNCATEGORIZED).
        
        Args:
            pdf_path: Path to PDF file
            doc_id: Document ID for logging
            
        Returns:
            Classification result dict with keys:
            - category: Category name (e.g., "ENGINEERING_DESIGN")
            - doc_type: Document type within category (e.g., "P&ID")
            - confidence: Confidence score (0.0-1.0)
            - status: Classification status ("classified" or "needs_review")
            - method: Classification method ("cadlike_gate" or "ai_classifier")
            
            Returns None if classification fails or is disabled.
        """
        if not self.enable_classification or not self._classification_pipeline:
            return None
        
        try:
            logger.debug(f"Running 4-category classification for {pdf_path.name}")
            
            # Run classification pipeline
            pipeline_result = self._classification_pipeline.classify_document(
                pdf_path=pdf_path,
                doc_metadata={"doc_id": doc_id}
            )
            
            # Extract classification result
            classification = pipeline_result.classification
            
            # Log classification decision
            if pipeline_result.guardrail_triggered:
                logger.info(
                    f"📋 Classification (guardrail): {pdf_path.name} -> "
                    f"{classification.category}/{classification.doc_type} "
                    f"(CAD_score={pipeline_result.cad_score:.3f})"
                )
                with self._stats_lock:
                    self.stats["classification_guardrail_triggered"] += 1
            else:
                logger.info(
                    f"📋 Classification (AI): {pdf_path.name} -> "
                    f"{classification.category}/{classification.doc_type} "
                    f"(confidence={classification.confidence:.2f})"
                )
            
            # Track needs_review status
            if classification.status == "needs_review":
                logger.warning(
                    f"⚠️ Classification needs review: {pdf_path.name} "
                    f"(confidence={classification.confidence:.2f})"
                )
                with self._stats_lock:
                    self.stats["classification_needs_review"] += 1
            
            # Update classification count
            with self._stats_lock:
                self.stats["classification_count"] += 1
            
            # Return as dict for metadata storage
            return classification.to_dict()
            
        except Exception as e:
            logger.error(f"Classification failed for {pdf_path.name}: {e}")
            logger.debug(f"Classification error details:", exc_info=True)
            
            # Return fallback result for failed classification
            return {
                "category": "UNCATEGORIZED",
                "doc_type": "Unknown",
                "confidence": 0.0,
                "status": "needs_review",
                "dominant_content": "unknown",
                "reasoning": f"Classification error: {str(e)}",
                "method": "error"
            }

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
                    # INJECT PAGE MARKER: Critical for citation accuracy
                    # This ensures text_chunker can attribute text to the correct page
                    page_text_with_marker = (
                        f"<!-- Page {page.page_num} -->\n{page.text}"
                    )

                    page_data = {
                        "page_num": (page.page_num - 1) if page.page_num else 0,
                        "full_text": page.text,
                        "blocks": [
                            {
                                "text": page_text_with_marker,
                                "structure_type": "paragraph",
                            }
                        ],
                    }
                    # Add tables if present
                    if page.tables:
                        page_data["tables"] = page.tables
                    extraction["pages"].append(page_data)
                md_result = converter.convert_with_structure(extraction)
                markdown_text = md_result["markdown"]
                structure_meta = md_result.get("structure", {})
        except Exception as e:
            logger.warning(
                f"Markdown converter failed, using plain text with page markers: {e}"
            )
            # INJECT PAGE MARKER in fallback path too
            markdown_text = "\n\n".join(
                f"<!-- Page {page.page_num} -->\n{page.text}" for page in pdf_doc.pages
            )
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
        chunk_strategy_override: Optional[str] = None,
        classification_result: Optional[Dict] = None,
    ) -> List[Dict]:
        """Create chunks from document

        Args:
            chunk_strategy_override: Override chunking strategy (for fallback modes)
            classification_result: Classification result dict with category, doc_type, confidence, status
        """
        # Prepare metadata
        metadata = {
            "doc_type": doc_type,
            "revision": revision,
            "source_format": pdf_doc.source_format,
            "file_name": pdf_doc.file_name,
            "title": pdf_doc.title,
            "author": pdf_doc.author,
        }
        
        # Add classification metadata (4-category taxonomy)
        if classification_result:
            metadata["category"] = classification_result.get("category")
            metadata["classification_doc_type"] = classification_result.get("doc_type")
            metadata["classification_status"] = classification_result.get("status")
            metadata["classification_confidence"] = classification_result.get("confidence")
            metadata["classification_method"] = classification_result.get("method")

        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        # Use override strategy if provided (for safe mode)
        effective_strategy = chunk_strategy_override or self.chunk_strategy

        # Choose HierarchicalChunker strategy per CLI or override
        chunker = HierarchicalChunker(
            max_chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            use_token_count=False,  # Use char count for consistency
            chunking_strategy=effective_strategy,
            sentence_window_size=self.sentence_window_size,
        )

        # CRITICAL FIX: Use page-aware chunking with index mapping
        # This fixes page metadata bug where chunks show wrong page numbers
        try:
            # Build list of (page_num, text) tuples from pdf_doc
            pages_list = []
            for page in pdf_doc.pages:
                # Remove page markers from text since chunk_markdown_with_pages adds them
                clean_text = page.text
                pages_list.append((page.page_num, clean_text))

            # Call new method with index mapping
            chunks = chunker.chunk_markdown_with_pages(pages_list, doc_id, metadata)
            logger.debug(
                f"Used page-aware chunking with index mapping for {len(pages_list)} pages"
            )
        except Exception as e:
            # Fallback to old method if page-aware chunking fails
            logger.warning(
                f"Page-aware chunking failed, falling back to regex-based: {e}"
            )
            chunks = chunker.chunk_markdown(markdown_text, doc_id, metadata)

        # Convert to dict format
        chunk_dicts = []

        # PERFORMANCE FIX: Initialize TagNormalizer ONCE outside the loop
        # Previously was instantiated per-chunk, causing massive CPU waste (5000 chunks = 5000 objects)
        _tag_normalizer = None
        try:
            from app.rag.normalizers.tag_normalizer import TagNormalizer

            _tag_normalizer = TagNormalizer(
                standardize_separator=False,  # Keep original separators (spaces, hyphens)
                remove_spaces=False,  # Preserve spaces in tags
                uppercase=True,  # Still uppercase for consistency
            )
        except Exception as e:
            # Non-fatal; proceed without tag extraction capability
            logger.debug(f"TagNormalizer not available: {e}")

        # SAFETY CAP: Maximum tags per chunk to prevent metadata explosion
        MAX_TAGS_PER_CHUNK = 50

        for chunk in chunks:
            chunk_dict = chunk.to_dict()
            # Ensure all metadata is present
            chunk_dict["metadata"].update(metadata)

            # Enrich with equipment tags using TagNormalizer (additive, safe)
            if _tag_normalizer is not None:
                try:
                    _tags = _tag_normalizer.extract_tags(chunk_dict.get("text") or "")
                    if _tags:
                        # Use "normalized" (uppercase only) as primary tags
                        normalized_tags = [
                            t.get("normalized") for t in _tags if t.get("normalized")
                        ]
                        raw_tags = [
                            t.get("original") for t in _tags if t.get("original")
                        ]
                        if normalized_tags:
                            seen = set()
                            norm_dedup = []
                            for t in normalized_tags:
                                if t not in seen:
                                    seen.add(t)
                                    norm_dedup.append(t)
                                # SAFETY CAP: Limit to prevent metadata explosion
                                if len(norm_dedup) >= MAX_TAGS_PER_CHUNK:
                                    break
                            chunk_dict["metadata"]["tags"] = norm_dedup[
                                :MAX_TAGS_PER_CHUNK
                            ]
                        if raw_tags:
                            preview = []
                            seen_raw = set()
                            for r in raw_tags:
                                r_str = str(r)
                                if r_str not in seen_raw:
                                    seen_raw.add(r_str)
                                    preview.append(r_str)
                                # SAFETY CAP: Limit raw tags preview
                                if len(preview) >= MAX_TAGS_PER_CHUNK:
                                    break
                            chunk_dict["metadata"]["tags_raw"] = preview[
                                :MAX_TAGS_PER_CHUNK
                            ]
                except Exception as e:
                    # Non-fatal; proceed without tags for this chunk
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

    def _build_layout_for_page(
        self, pdf_path: Path, page_num: int, doc_id: str
    ) -> Optional[object]:
        """
        Build PageLayout for a single page (for spatial indexing)

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-based)
            doc_id: Document ID

        Returns:
            PageLayout object or None if failed
        """
        try:
            from app.ingestion.layout.page_layout_builder import PageLayoutBuilder

            # Initialize PageLayoutBuilder (reuse from Tag Extraction)
            layout_builder = PageLayoutBuilder(
                enable_ocr=True,
                enable_drawings=True,
                enable_shape_aware=self.config.ENABLE_SHAPE_AWARE_ROI
                if hasattr(self, "config")
                else False,
            )

            # Build layout for this page
            layout = layout_builder.build_layout(pdf_path, page_num, doc_id)

            # Optionally save layout for future reuse
            from app.config import get_config

            config = get_config()
            layout_builder.save_layout(layout, config.LAYOUT_DIR)

            logger.debug(f"Built new layout for page {page_num}")
            return layout

        except Exception as e:
            logger.error(f"Failed to build layout for page {page_num}: {e}")
            return None

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
        "--enable-ocr",
        action="store_true",
        default=True,
        help="Enable OCR for scanned pages (default: True, requires Google Cloud Vision credentials)",
    )

    parser.add_argument(
        "--no-ocr",
        action="store_false",
        dest="enable_ocr",
        help="Disable OCR (not recommended)",
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

    parser.add_argument(
        "--enable-classification",
        action="store_true",
        default=True,
        help="Enable 4-category document classification (default: True)",
    )

    parser.add_argument(
        "--no-classification",
        action="store_false",
        dest="enable_classification",
        help="Disable 4-category document classification",
    )

    parser.add_argument(
        "--profile",
        type=str,
        choices=["full", "fast", "minimal"],
        default=None,
        help="Use preset configuration profile (full: OCR+PID+Tables, fast: PID+Tables, minimal: basic only)",
    )

    args = parser.parse_args()

    # Apply profile presets (can be overridden by explicit flags)
    if args.profile == "full":
        logger.info("Using 'full' profile: OCR + PID Tags + Table Extraction")
        if not any(["--enable-ocr" in sys.argv, "--no-ocr" in sys.argv]):
            args.enable_ocr = True
        if "--enable-pid-tags" not in sys.argv:
            args.enable_pid_tags = True
        if not any(["--extract-tables" in sys.argv, "--no-extract-tables" in sys.argv]):
            args.extract_tables = True
    elif args.profile == "fast":
        logger.info("Using 'fast' profile: PID Tags + Table Extraction (no OCR)")
        if not any(["--enable-ocr" in sys.argv, "--no-ocr" in sys.argv]):
            args.enable_ocr = False
        if "--enable-pid-tags" not in sys.argv:
            args.enable_pid_tags = True
        if not any(["--extract-tables" in sys.argv, "--no-extract-tables" in sys.argv]):
            args.extract_tables = True
    elif args.profile == "minimal":
        logger.info("Using 'minimal' profile: Basic text extraction only")
        if not any(["--enable-ocr" in sys.argv, "--no-ocr" in sys.argv]):
            args.enable_ocr = False
        if "--enable-pid-tags" not in sys.argv:
            args.enable_pid_tags = False
        if not any(["--extract-tables" in sys.argv, "--no-extract-tables" in sys.argv]):
            args.extract_tables = False

    # Validate source directory
    if not args.source_dir.exists():
        logger.error(f"Source directory does not exist: {args.source_dir}")
        sys.exit(1)

    # Check OCR availability if requested (Google Cloud Vision)
    if args.enable_ocr:
        try:
            from google.cloud import vision

            from app.ingestion.pdf_processor import OCR_AVAILABLE

            # Check if credentials are set
            creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if not creds:
                logger.warning(
                    "OCR requested but GOOGLE_APPLICATION_CREDENTIALS not set. Continuing without OCR..."
                )
                args.enable_ocr = False
            elif not Path(creds).exists():
                logger.warning(
                    f"OCR requested but credentials file not found: {creds}. Continuing without OCR..."
                )
                args.enable_ocr = False
            elif not OCR_AVAILABLE:
                logger.warning(
                    "OCR requested but Google Cloud Vision API not available. Continuing without OCR..."
                )
                args.enable_ocr = False
            else:
                logger.info(f"OCR enabled using Google Cloud Vision API")
        except ImportError as e:
            logger.warning(
                f"OCR requested but Google Cloud Vision API not available: {e}. Continuing without OCR..."
            )
            args.enable_ocr = False

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
        enable_classification=args.enable_classification,
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
