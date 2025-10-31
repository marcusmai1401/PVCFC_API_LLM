"""
Build Page Index Tool - Phase 1 Citation Accuracy
Extracts page-level text from PDFs, creates text_by_page.jsonl and BM25 page index

Usage:
    python tools/build_page_index.py --doc-id-map artifacts/ingestion/doc_id_map.json
    python tools/build_page_index.py --help
"""

import argparse
import io
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path
from pathlib import Path as _Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import jsonlines
import numpy as np
from loguru import logger
from PIL import Image
from rank_bm25 import BM25Okapi
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

# Ensure project root is on sys.path when running as a script
try:
    _PROJECT_ROOT = _Path(__file__).resolve().parents[1]
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))
except Exception as _e:
    logger.debug(f"Failed to set project root on sys.path: {_e}")

# Import centralized config
try:
    from app.config import get_config

    _pipeline_config = get_config()
except ImportError as _cfg_err:
    _pipeline_config = None
    logger.warning(f"Failed to import config: {_cfg_err}")

# Import shared text processing utilities
try:
    from app.utils.text_processing import preprocess_text_for_bm25, tokenize_for_bm25

    TEXT_PROCESSING_AVAILABLE = True
except ImportError as _txt_err:
    TEXT_PROCESSING_AVAILABLE = False
    logger.warning(f"Text processing utils not available: {_txt_err}")

# Import OCR support
try:
    from app.ingestion.paddle_ocr_config import get_paddleocr_instance

    OCR_AVAILABLE = True
except ImportError as _imp_err:
    OCR_AVAILABLE = False
    logger.warning("PaddleOCR not available, scanned PDFs will not be processed")
    logger.debug(f"ImportError details: {_imp_err}")

# Initialize
console = Console()


class PageIndexBuilder:
    """Build page-level index from PDF documents"""

    def __init__(
        self,
        doc_id_map_path: str,
        output_dir: Optional[str] = None,
        enable_ocr: bool = True,
        min_text_length: Optional[int] = None,
        ocr_trigger_threshold: Optional[int] = None,
        ocr_min_confidence: Optional[float] = None,
    ):
        """
        Initialize PageIndexBuilder

        Args:
            doc_id_map_path: Path to doc_id_map.json
            output_dir: Output directory for generated files (defaults from config)
            enable_ocr: Enable OCR for scanned PDFs
            min_text_length: Minimum chars to keep page (defaults from config)
            ocr_trigger_threshold: Trigger OCR if page has < this many chars (defaults from config)
            ocr_min_confidence: Minimum OCR confidence 0-1 scale (defaults from config)
        """
        self.doc_id_map_path = Path(doc_id_map_path)

        # Use config defaults if available
        if _pipeline_config:
            self.output_dir = (
                Path(output_dir) if output_dir else _pipeline_config.ARTIFACTS_DIR
            )
            self.min_text_length = (
                min_text_length
                if min_text_length is not None
                else _pipeline_config.MIN_TEXT_LENGTH
            )
            self.ocr_trigger_threshold = (
                ocr_trigger_threshold
                if ocr_trigger_threshold is not None
                else _pipeline_config.OCR_TRIGGER_THRESHOLD
            )
            self.ocr_min_confidence = (
                ocr_min_confidence
                if ocr_min_confidence is not None
                else _pipeline_config.OCR_MIN_CONFIDENCE
            )
        else:
            # Fallback to hardcoded defaults
            self.output_dir = (
                Path(output_dir)
                if output_dir
                else Path("artifacts/ingestion_production")
            )
            self.min_text_length = (
                min_text_length if min_text_length is not None else 10
            )
            self.ocr_trigger_threshold = (
                ocr_trigger_threshold if ocr_trigger_threshold is not None else 40
            )
            self.ocr_min_confidence = (
                ocr_min_confidence if ocr_min_confidence is not None else 0.3
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.enable_ocr = enable_ocr and OCR_AVAILABLE

        # Initialize OCR if enabled
        self.ocr_engine = None
        if self.enable_ocr:
            try:
                self.ocr_engine = get_paddleocr_instance()
                logger.info("✅ PaddleOCR initialized for scanned PDF support")
            except Exception as e:
                logger.warning(f"Failed to initialize OCR: {e}")
                self.enable_ocr = False

        # Output paths
        self.text_by_page_path = self.output_dir / "text_by_page.jsonl"
        self.page_index_path = self.output_dir / "page_bm25_index.pkl"
        self.page_metadata_path = self.output_dir / "page_metadata.json"

        # Stats
        self.stats = {
            "total_docs": 0,
            "processed_docs": 0,
            "total_pages": 0,
            "empty_pages": 0,
            "ocr_pages": 0,
            "error_docs": 0,
            "extraction_time": 0.0,
        }

    def load_doc_id_map(self) -> Dict:
        """Load doc_id_map.json"""
        if not self.doc_id_map_path.exists():
            raise FileNotFoundError(f"doc_id_map not found: {self.doc_id_map_path}")

        logger.info(f"Loading doc_id_map from {self.doc_id_map_path}")
        with open(self.doc_id_map_path, "r", encoding="utf-8") as f:
            doc_id_map = json.load(f)

        logger.info(f"Loaded {len(doc_id_map)} documents")
        return doc_id_map

    def extract_page_text(self, pdf_path: Path, doc_id: str) -> List[Dict]:
        """
        Extract text from each page of a PDF

        Args:
            pdf_path: Path to PDF file
            doc_id: Document ID

        Returns:
            List of page dictionaries
        """
        pages_data = []

        try:
            doc = fitz.open(str(pdf_path))

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_index = page_num + 1  # 1-indexed

                # Extract text
                text = page.get_text("text")
                char_count = len(text)

                # If text is empty or very short, try OCR for scanned PDFs
                # Use ocr_trigger_threshold (default 40) to match ingestion pipeline
                if char_count < self.ocr_trigger_threshold and self.enable_ocr:
                    ocr_text = self._perform_ocr(page)
                    if ocr_text and len(ocr_text) > char_count:
                        text = ocr_text
                        char_count = len(text)
                        self.stats["ocr_pages"] += 1

                # Skip pages with insufficient text
                # Use min_text_length (default 10) to match ingestion pipeline
                if char_count < self.min_text_length:
                    self.stats["empty_pages"] += 1
                    continue

                # Basic statistics
                word_count = len(text.split())

                # Detect tables and figures
                has_tables = self._detect_tables(page)
                has_figures = self._detect_figures(page)

                # Get page dimensions
                rect = page.rect
                page_width = rect.width
                page_height = rect.height

                # Build page data
                page_data = {
                    "doc_id": doc_id,
                    "page": page_index,
                    "text": text,
                    "char_count": char_count,
                    "word_count": word_count,
                    "has_tables": has_tables,
                    "has_figures": has_figures,
                    "metadata": {
                        "source_path": str(pdf_path),
                        "extraction_method": "pymupdf",
                        "extraction_date": datetime.utcnow().isoformat() + "Z",
                        "page_width": page_width,
                        "page_height": page_height,
                    },
                }

                pages_data.append(page_data)
                self.stats["total_pages"] += 1

            doc.close()
            self.stats["processed_docs"] += 1

        except Exception as e:
            logger.error(f"Error extracting from {pdf_path}: {e}")
            self.stats["error_docs"] += 1

        return pages_data

    def _detect_tables(self, page) -> bool:
        """
        Detect if page contains tables

        Simple heuristic: Check for text blocks in grid-like layout
        """
        try:
            # Get text blocks
            blocks = page.get_text("dict")["blocks"]

            # Check for multiple aligned blocks (simple grid detection)
            if len(blocks) > 10:
                # If many blocks, likely has tables
                return True

            return False
        except:
            return False

    def _detect_figures(self, page) -> bool:
        """Detect if page contains figures/images"""
        try:
            images = page.get_images()
            return len(images) > 0
        except:
            return False

    def _perform_ocr(self, page) -> str:
        """Perform OCR on a PDF page using PaddleOCR"""
        if not self.enable_ocr or not self.ocr_engine:
            return ""

        try:
            # Render page to image
            mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.pil_tobytes(format="PNG")
            image = Image.open(io.BytesIO(img_data))

            # Convert PIL Image to numpy array for PaddleOCR
            img_array = np.array(image)

            # Perform OCR with PaddleOCR
            result = self.ocr_engine.ocr(img_array, cls=True)

            # Extract text from PaddleOCR results
            # PaddleOCR returns: [[[box], (text, confidence)], ...] or [[None]]
            text_parts = []
            if result and len(result) > 0:
                page_result = result[0]  # First element is page result
                if page_result and page_result != [None]:  # Check for valid result
                    for line in page_result:
                        if line and len(line) >= 2:
                            # line structure: [box_coords, (text, confidence)]
                            text_info = line[1]
                            if text_info and len(text_info) >= 2:
                                text, confidence = text_info[0], text_info[1]
                                # Filter by confidence threshold (default 0.3 = 30%)
                                if (
                                    confidence >= self.ocr_min_confidence
                                    and text
                                    and text.strip()
                                ):
                                    text_parts.append(text)

            # Join text parts with spaces
            ocr_text = " ".join(text_parts)
            return ocr_text

        except Exception as e:
            logger.debug(f"OCR failed for page: {e}")
            return ""

    def build_text_by_page(self, doc_id_map: Dict) -> None:
        """
        Extract page text from all PDFs and write to text_by_page.jsonl

        Args:
            doc_id_map: Mapping of doc_id to document info
        """
        logger.info(f"Building text_by_page.jsonl from {len(doc_id_map)} documents")

        self.stats["total_docs"] = len(doc_id_map)

        with jsonlines.open(self.text_by_page_path, mode="w") as writer:
            # Create progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "[cyan]Extracting pages...", total=len(doc_id_map)
                )

                for doc_id, doc_info in doc_id_map.items():
                    # Handle both formats: string path or dict with pdf_path
                    if isinstance(doc_info, str):
                        pdf_path = doc_info
                    elif isinstance(doc_info, dict):
                        pdf_path = doc_info.get("pdf_path")
                    else:
                        logger.warning(f"Invalid doc_info type for {doc_id}, skipping")
                        progress.advance(task)
                        continue

                    if not pdf_path:
                        logger.warning(f"No pdf_path for {doc_id}, skipping")
                        progress.advance(task)
                        continue

                    pdf_file = Path(pdf_path)
                    if not pdf_file.exists():
                        logger.warning(f"PDF not found: {pdf_path}, skipping")
                        progress.advance(task)
                        continue

                    # Extract pages
                    pages_data = self.extract_page_text(pdf_file, doc_id)

                    # Write to JSONL
                    for page_data in pages_data:
                        writer.write(page_data)

                    progress.advance(task)

        logger.info(
            f"✅ Wrote {self.stats['total_pages']} pages to {self.text_by_page_path}"
        )

    def build_bm25_index(self) -> None:
        """Build BM25 index from text_by_page.jsonl"""
        logger.info("Building BM25 page index...")

        if not self.text_by_page_path.exists():
            raise FileNotFoundError(
                f"text_by_page.jsonl not found: {self.text_by_page_path}"
            )

        # Load pages
        corpus = []
        doc_ids = []
        pages = []

        with jsonlines.open(self.text_by_page_path) as reader:
            for obj in reader:
                doc_id = obj["doc_id"]
                page = obj["page"]
                text = obj["text"]

                # Preprocess text for BM25
                processed_text = self._preprocess_text(text)

                corpus.append(processed_text)
                doc_ids.append(doc_id)
                pages.append(page)

        logger.info(f"Loaded {len(corpus)} pages for indexing")

        # Tokenize corpus using shared function
        if TEXT_PROCESSING_AVAILABLE:
            tokenized_corpus = [tokenize_for_bm25(text) for text in corpus]
            logger.info(
                "Using shared tokenization function (consistent with query processing)"
            )
        else:
            # Fallback to simple tokenization
            tokenized_corpus = [text.split() for text in corpus]
            logger.warning(
                "Using fallback tokenization (text_processing not available)"
            )

        # Build BM25
        bm25 = BM25Okapi(tokenized_corpus)

        # Save index
        index_data = {
            "corpus": corpus,
            "doc_ids": doc_ids,
            "pages": pages,
            "bm25": bm25,
        }

        with open(self.page_index_path, "wb") as f:
            pickle.dump(index_data, f)

        logger.info(f"✅ BM25 index saved to {self.page_index_path}")

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for BM25 indexing

        Rules:
        - Lowercase conversion
        - Keep numbers and technical terms (e.g., KT-06101, 150psi)
        """
        if TEXT_PROCESSING_AVAILABLE:
            return preprocess_text_for_bm25(text)
        else:
            # Fallback to simple preprocessing
            text = text.lower()
            return text

    def build_metadata_index(self) -> None:
        """Build page metadata index from text_by_page.jsonl"""
        logger.info("Building page metadata index...")

        if not self.text_by_page_path.exists():
            raise FileNotFoundError(
                f"text_by_page.jsonl not found: {self.text_by_page_path}"
            )

        metadata_index = {}

        with jsonlines.open(self.text_by_page_path) as reader:
            for obj in reader:
                doc_id = obj["doc_id"]
                page = obj["page"]

                # Initialize doc entry if needed
                if doc_id not in metadata_index:
                    metadata_index[doc_id] = {
                        "total_pages": 0,
                        "pages": {},
                    }

                # Add page metadata
                metadata_index[doc_id]["pages"][str(page)] = {
                    "char_count": obj["char_count"],
                    "word_count": obj["word_count"],
                    "has_tables": obj["has_tables"],
                    "has_figures": obj["has_figures"],
                }

        # Count total pages per doc
        for doc_id in metadata_index:
            metadata_index[doc_id]["total_pages"] = len(metadata_index[doc_id]["pages"])

        # Save metadata index
        with open(self.page_metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata_index, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Metadata index saved to {self.page_metadata_path}")

    def run(self) -> None:
        """Run full page index build pipeline"""
        import time

        start_time = time.time()

        console.rule("[bold cyan]Page Index Builder - Phase 1")
        console.print()

        # Step 1: Load doc_id_map
        console.print("📖 [bold]Step 1:[/bold] Loading doc_id_map...")
        doc_id_map = self.load_doc_id_map()
        console.print(f"   ✅ Loaded {len(doc_id_map)} documents\n")

        # Step 2: Extract page text
        console.print("📄 [bold]Step 2:[/bold] Extracting page-level text from PDFs...")
        self.build_text_by_page(doc_id_map)
        console.print(
            f"   ✅ Extracted {self.stats['total_pages']} pages from {self.stats['processed_docs']} documents\n"
        )

        # Step 3: Build BM25 index
        console.print("🔍 [bold]Step 3:[/bold] Building BM25 page index...")
        self.build_bm25_index()
        console.print(f"   ✅ BM25 index built successfully\n")

        # Step 4: Build metadata index
        console.print("📊 [bold]Step 4:[/bold] Building page metadata index...")
        self.build_metadata_index()
        console.print(f"   ✅ Metadata index built successfully\n")

        # Final stats
        elapsed = time.time() - start_time
        self.stats["extraction_time"] = elapsed

        self._print_summary()

    def _print_summary(self) -> None:
        """Print summary statistics"""
        console.rule("[bold green]Build Complete!")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", width=30)
        table.add_column("Value", style="green", width=20)

        table.add_row("Total Documents", str(self.stats["total_docs"]))
        table.add_row("Processed Documents", str(self.stats["processed_docs"]))
        table.add_row("Total Pages Indexed", str(self.stats["total_pages"]))
        table.add_row("OCR Pages", str(self.stats["ocr_pages"]))
        table.add_row("Empty Pages Skipped", str(self.stats["empty_pages"]))
        table.add_row("Error Documents", str(self.stats["error_docs"]))
        table.add_row("Build Time", f"{self.stats['extraction_time']:.2f} seconds")

        console.print()
        console.print(table)
        console.print()

        # Output files
        console.print("[bold]📁 Output Files:[/bold]")
        console.print(f"   • text_by_page.jsonl: {self.text_by_page_path}")
        console.print(f"   • BM25 index:         {self.page_index_path}")
        console.print(f"   • Metadata index:     {self.page_metadata_path}")
        console.print()

        console.print(
            "[bold green]✅ Page index build completed successfully![/bold green]"
        )
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("   1. Verify text_by_page.jsonl content")
        console.print("   2. Test page reranking with sample queries")
        console.print("   3. Integrate page_reranker into RAG pipeline")
        console.print()


def cmd_build(args):
    """
    Build page-level index from PDFs

    Extracts text from each page, creates text_by_page.jsonl,
    builds BM25 index, and generates metadata index.
    """
    try:
        builder = PageIndexBuilder(
            doc_id_map_path=args.doc_id_map,
            output_dir=args.output_dir,
            enable_ocr=not args.no_ocr,  # Invert no_ocr flag
            min_text_length=args.min_text_length,
            ocr_trigger_threshold=args.ocr_trigger_threshold,
            ocr_min_confidence=args.ocr_min_confidence,
        )
        builder.run()

    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        logger.exception("Build failed")
        return 1
    return 0


def cmd_stats(args):
    """Show statistics for existing text_by_page.jsonl"""
    text_by_page_path = Path(args.text_by_page)

    if not text_by_page_path.exists():
        console.print(f"[bold red]❌ File not found:[/bold red] {text_by_page_path}")
        return 1

    console.print(f"📊 Analyzing {text_by_page_path}...")
    console.print()

    total_pages = 0
    doc_pages = {}
    total_chars = 0
    total_words = 0
    pages_with_tables = 0
    pages_with_figures = 0

    with jsonlines.open(text_by_page_path) as reader:
        for obj in reader:
            total_pages += 1
            doc_id = obj["doc_id"]
            doc_pages[doc_id] = doc_pages.get(doc_id, 0) + 1

            total_chars += obj["char_count"]
            total_words += obj["word_count"]

            if obj["has_tables"]:
                pages_with_tables += 1
            if obj["has_figures"]:
                pages_with_figures += 1

    # Print stats
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", width=40)
    table.add_column("Value", style="green", width=20)

    table.add_row("Total Pages", str(total_pages))
    table.add_row("Total Documents", str(len(doc_pages)))
    table.add_row("Avg Pages per Doc", f"{total_pages / len(doc_pages):.1f}")
    table.add_row("Total Characters", f"{total_chars:,}")
    table.add_row("Total Words", f"{total_words:,}")
    table.add_row("Avg Chars per Page", f"{total_chars / total_pages:.0f}")
    table.add_row("Avg Words per Page", f"{total_words / total_pages:.0f}")
    table.add_row(
        "Pages with Tables",
        f"{pages_with_tables} ({pages_with_tables/total_pages*100:.1f}%)",
    )
    table.add_row(
        "Pages with Figures",
        f"{pages_with_figures} ({pages_with_figures/total_pages*100:.1f}%)",
    )

    console.print(table)
    console.print()

    # Show top 10 docs by page count
    console.print("[bold]Top 10 Documents by Page Count:[/bold]")
    top_docs = sorted(doc_pages.items(), key=lambda x: x[1], reverse=True)[:10]

    for i, (doc_id, count) in enumerate(top_docs, 1):
        doc_id_short = doc_id[:60] + "..." if len(doc_id) > 60 else doc_id
        console.print(f"   {i:2d}. {doc_id_short:60s} - {count:3d} pages")

    console.print()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build page-level index from PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Build command
    build_parser = subparsers.add_parser(
        "build",
        help="Build page-level index from PDFs",
    )
    build_parser.add_argument(
        "--doc-id-map",
        "-d",
        default="artifacts/ingestion/doc_id_map.json",
        help="Path to doc_id_map.json (default: artifacts/ingestion/doc_id_map.json)",
    )
    build_parser.add_argument(
        "--output-dir",
        "-o",
        default="artifacts/ingestion_production",
        help="Output directory for page index files (default: artifacts/ingestion_production)",
    )
    build_parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR for scanned PDFs (faster but skips scanned documents)",
    )
    build_parser.add_argument(
        "--min-text-length",
        type=int,
        default=10,
        help="Minimum chars to keep page (default: 10, matches ingestion pipeline)",
    )
    build_parser.add_argument(
        "--ocr-trigger-threshold",
        type=int,
        default=40,
        help="Trigger OCR if page has < this many chars (default: 40)",
    )
    build_parser.add_argument(
        "--ocr-min-confidence",
        type=float,
        default=0.3,
        help="Minimum OCR confidence 0-1 scale (default: 0.3 = 30%%)",
    )

    # Stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show statistics for existing text_by_page.jsonl",
    )
    stats_parser.add_argument(
        "--text-by-page",
        "-t",
        default="artifacts/ingestion_production/text_by_page.jsonl",
        help="Path to text_by_page.jsonl (default: artifacts/ingestion_production/text_by_page.jsonl)",
    )

    args = parser.parse_args()

    if args.command == "build":
        exit(cmd_build(args))
    elif args.command == "stats":
        exit(cmd_stats(args))
    else:
        parser.print_help()
        exit(1)
