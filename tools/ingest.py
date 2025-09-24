#!/usr/bin/env python
"""
Ingestion Pipeline CLI Tool
Processes PDFs with multithreading, OCR support, and JSONL output
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger

from app.ingestion.document_classifier import DocumentClassifier
from app.ingestion.ocr_config import get_ocr_status
from app.ingestion.pdf_processor import PageContent, PDFDocument, PDFProcessor
from app.rag.chunkers.hierarchical_chunker import HierarchicalChunker


class IngestionPipeline:
    """
    Multithreaded ingestion pipeline for PDF processing
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
    ):
        """
        Initialize ingestion pipeline

        Args:
            source_dir: Directory containing PDFs to process
            output_dir: Directory for outputs
            workers: Number of worker threads (None for auto)
            enable_ocr: Enable OCR for scanned pages
            ocr_language: Language for OCR
            parser: Parser to use ('auto', 'pymupdf', 'unstructured')
            emit_jsonl: Emit JSONL outputs in addition to JSON
            chunk_size: Target chunk size
            chunk_overlap: Overlap between chunks
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

        # Initialize document classifier
        self.classifier = DocumentClassifier()

        # Thread-safe JSONL writer lock
        self._jsonl_lock = threading.Lock()

        # Locks for thread safety
        self._jsonl_lock = threading.Lock()
        self._stats_lock = threading.Lock()

        # Track processing stats
        self.stats = {
            "total_pdfs": 0,
            "processed": 0,
            "failed": 0,
            "scanned_pages": 0,
            "vector_pages": 0,
            "total_chunks": 0,
            "start_time": None,
            "end_time": None,
        }

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
        logger.info("Starting Ingestion Pipeline")
        logger.info(f"Source: {self.source_dir}")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Workers: {self.workers}")
        logger.info(f"OCR: {self.enable_ocr}")
        logger.info(f"Parser: {self.parser}")
        logger.info(f"Chunk strategy: {self.chunk_strategy}")
        logger.info("=" * 80)

        self.stats["start_time"] = datetime.now()

        # Ensure output directories exist
        self._setup_output_dirs()

        # Find all PDFs
        pdf_files = list(self.source_dir.rglob("*.pdf"))
        self.stats["total_pdfs"] = len(pdf_files)

        if not pdf_files:
            logger.warning("No PDF files found in source directory")
            return self.stats

        logger.info(f"Found {len(pdf_files)} PDF files to process")

        # Initialize manifests
        corpus_manifest = []
        checksums_manifest = []

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
                        corpus_entry, checksum_entry, counts = result
                        corpus_manifest.append(corpus_entry)
                        checksums_manifest.append(checksum_entry)
                        # Aggregate stats safely in main thread
                        self.stats["processed"] += 1
                        self.stats["total_chunks"] += counts.get("chunks", 0)
                        self.stats["scanned_pages"] += counts.get("scanned_pages", 0)
                        self.stats["vector_pages"] += counts.get("vector_pages", 0)

                        logger.info(
                            f"[{self.stats['processed']}/{self.stats['total_pdfs']}] "
                            f"Processed: {pdf_path.name}"
                        )
                except Exception as e:
                    logger.error(f"Failed to process {pdf_path.name}: {e}")
                    self.stats["failed"] += 1

        # Write manifests
        self._write_manifests(corpus_manifest, checksums_manifest)

        self.stats["end_time"] = datetime.now()
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        # Print summary
        logger.info("=" * 80)
        logger.info("Ingestion Pipeline Complete")
        logger.info(f"Total PDFs: {self.stats['total_pdfs']}")
        logger.info(f"Processed: {self.stats['processed']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Total chunks: {self.stats['total_chunks']}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Throughput: {self.stats['processed']/duration:.2f} PDFs/second")
        logger.info("=" * 80)

        return self.stats

    def _process_single_pdf(
        self, pdf_path: Path
    ) -> Optional[Tuple[Dict, Dict, Dict[str, int]]]:
        """
        Process a single PDF (thread-safe)

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (corpus_entry, checksum_entry, counts) or None if failed
        """
        try:
            # Calculate file checksum
            file_hash = self._calculate_file_hash(pdf_path)

            # Check if already processed (via checksum)
            if self._is_already_processed(file_hash):
                logger.debug(f"Skipping {pdf_path.name} - already processed")
                return None

            pdf_doc: Optional[PDFDocument] = None

            # Parser selection
            if self.parser == "unstructured":
                pdf_doc = self._process_with_unstructured(pdf_path)
            else:
                # Default to PyMuPDF (+ optional OCR)
                processor = PDFProcessor(
                    enable_ocr=self.enable_ocr,
                    ocr_language=self.ocr_language,
                    ocr_min_confidence=30.0,
                )
                pdf_doc = processor.process_pdf(pdf_path)

                # Auto fallback to unstructured when no text extracted
                if self.parser == "auto" and pdf_doc.num_pages == 0:
                    try:
                        import unstructured  # type: ignore

                        logger.info("Auto parser fallback: trying unstructured parser")
                        pdf_doc = self._process_with_unstructured(pdf_path)
                    except ImportError:
                        logger.debug("Unstructured not installed; skipping fallback")

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

            # Count pages by source_format (coarse)
            scanned_count = pdf_doc.num_pages if pdf_doc.source_format == "scan" else 0
            vector_count = pdf_doc.num_pages if pdf_doc.source_format == "vector" else 0

            # Create manifest entries
            corpus_entry = {
                "doc_id": doc_id,
                "file_path": str(pdf_path),
                "hash_sha256": file_hash,
                "pages": pdf_doc.num_pages,
                "doc_type": doc_type,
                "revision": revision,
                "source_format": pdf_doc.source_format,
                "ingested_at": datetime.now().isoformat(),
            }

            checksum_entry = {
                "file_path": str(pdf_path),
                "hash_sha256": file_hash,
                "last_modified": int(pdf_path.stat().st_mtime),
            }

            counts = {
                "chunks": len(chunks),
                "scanned_pages": scanned_count,
                "vector_pages": vector_count,
            }

            return corpus_entry, checksum_entry, counts

        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            return None

    def _process_with_unstructured(self, pdf_path: Path) -> PDFDocument:
        """Process a PDF using unstructured.io to extract page texts"""
        try:
            from unstructured.partition.pdf import partition_pdf  # type: ignore
        except ImportError as e:
            raise RuntimeError("unstructured package is not installed") from e

        logger.info(f"Processing with unstructured: {pdf_path}")
        elements = partition_pdf(filename=str(pdf_path))

        # Group text by page number
        from collections import defaultdict

        pages_map = defaultdict(list)
        for el in elements:
            text = getattr(el, "text", None)
            if not text:
                continue
            meta = getattr(el, "metadata", None)
            page_num = getattr(meta, "page_number", None) if meta else None
            # Default to page 1 if missing
            page_index = int(page_num) if page_num else 1
            pages_map[page_index].append(text)

        # Build PageContent list
        pages: List[PageContent] = []
        total_chars = 0
        total_words = 0
        for page_num in sorted(pages_map.keys()):
            page_text = "\n".join(pages_map[page_num]).strip()
            char_count = len(page_text)
            word_count = len(page_text.split())
            line_count = len(page_text.splitlines())
            total_chars += char_count
            total_words += word_count
            pages.append(
                PageContent(
                    page_num=page_num,
                    text=page_text,
                    char_count=char_count,
                    word_count=word_count,
                    line_count=line_count,
                    tables=None,
                    images=None,
                )
            )

        # Create PDFDocument (metadata limited)
        pdf_doc = PDFDocument(
            file_path=str(pdf_path),
            file_name=pdf_path.name,
            title=None,
            author=None,
            subject=None,
            keywords=None,
            creator=None,
            producer=None,
            creation_date=None,
            modification_date=None,
            num_pages=len(pages),
            total_chars=total_chars,
            total_words=total_words,
            pages=pages,
            processing_timestamp=datetime.now().isoformat(),
            source_format="vector",
        )

        logger.info(f"Unstructured extracted {len(pages)} pages, {total_words} words")
        return pdf_doc

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _is_already_processed(self, file_hash: str) -> bool:
        """Check if file was already processed based on checksum"""
        checksums_file = self.output_dir / "manifests" / "checksums.jsonl"
        if not checksums_file.exists():
            return False

        try:
            with open(checksums_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("hash_sha256") == file_hash:
                        return True
        except:
            pass

        return False

    def _generate_doc_id(self, pdf_path: Path, pdf_doc: PDFDocument) -> str:
        """Generate unique document ID"""
        # Use relative path from source_dir if possible
        try:
            rel_path = pdf_path.relative_to(self.source_dir)
            base_id = str(rel_path.with_suffix("")).replace("\\", "/")
        except:
            base_id = pdf_path.stem

        # Clean and truncate
        base_id = base_id.replace(" ", "_")[:50]

        # Add hash suffix for uniqueness
        hash_suffix = hashlib.md5(str(pdf_path).encode()).hexdigest()[:8]

        return f"{base_id}_{hash_suffix}"

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

            use_vector = (
                self.parser in ("auto", "pymupdf") and pdf_doc.source_format == "vector"
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
                # Simple conversion from pdf_doc pages (unstructured)
                extraction = {"file_path": pdf_doc.file_path, "pages": []}
                for page in pdf_doc.pages:
                    extraction["pages"].append(
                        {
                            "page_num": (page.page_num - 1) if page.page_num else 0,
                            "full_text": page.text,
                            "blocks": [
                                {"text": page.text, "structure_type": "paragraph"}
                            ],
                        }
                    )
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
        """Write manifest files by merging with existing entries (idempotent)"""
        corpus_file = self.output_dir / "manifests" / "corpus.jsonl"
        checksums_file = self.output_dir / "manifests" / "checksums.jsonl"

        # Load existing entries
        existing_corpus: List[Dict] = []
        existing_checksums: List[Dict] = []

        if corpus_file.exists():
            try:
                with open(corpus_file, "r", encoding="utf-8") as f:
                    for line in f:
                        existing_corpus.append(json.loads(line))
            except Exception as e:
                logger.warning(f"Failed to read existing corpus manifest: {e}")

        if checksums_file.exists():
            try:
                with open(checksums_file, "r", encoding="utf-8") as f:
                    for line in f:
                        existing_checksums.append(json.loads(line))
            except Exception as e:
                logger.warning(f"Failed to read existing checksums manifest: {e}")

        # Merge and de-duplicate
        merged_corpus_map = {}
        for entry in existing_corpus + corpus:
            key = (entry.get("file_path"), entry.get("hash_sha256"))
            merged_corpus_map[key] = entry  # prefer latest
        merged_corpus = list(merged_corpus_map.values())

        merged_checksums_map = {}
        for entry in existing_checksums + checksums:
            key = (entry.get("file_path"), entry.get("hash_sha256"))
            merged_checksums_map[key] = entry
        merged_checksums = list(merged_checksums_map.values())

        # Write corpus manifest
        temp_file = corpus_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            for entry in merged_corpus:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        temp_file.replace(corpus_file)

        # Write checksums manifest
        temp_file = checksums_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            for entry in merged_checksums:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        temp_file.replace(checksums_file)

        logger.info(f"Wrote {len(merged_corpus)} entries to corpus manifest")
        logger.info(f"Wrote {len(merged_checksums)} entries to checksums manifest")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest PDF documents with multithreading and OCR support"
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
        "--ocr-lang", type=str, default="eng", help="Language for OCR (default: eng)"
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

    args = parser.parse_args()

    # Validate source directory
    if not args.source_dir.exists():
        logger.error(f"Source directory does not exist: {args.source_dir}")
        sys.exit(1)

    # Check OCR availability if requested
    if args.enable_ocr:
        from app.ingestion.ocr_config import get_ocr_status

        ocr_status = get_ocr_status()
        if not ocr_status["ocr_enabled"]:
            logger.warning("OCR requested but not available:")
            logger.warning(
                f"  Tesseract available: {ocr_status['tesseract_available']}"
            )
            logger.warning(
                f"  pytesseract installed: {ocr_status['pytesseract_installed']}"
            )
            logger.warning("Continuing without OCR...")
            args.enable_ocr = False
        else:
            logger.info(f"OCR enabled with Tesseract {ocr_status['tesseract_version']}")

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
    )

    stats = pipeline.run()

    # Exit with appropriate code
    if stats["failed"] > 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
