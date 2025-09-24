"""
PDF Processing Module for Document Ingestion
Handles PDF text extraction, metadata extraction, and page-level processing
"""
import hashlib
import json
import pickle
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from loguru import logger

# Import OCR configuration
try:
    from .ocr_config import OCR_AVAILABLE, get_ocr_status, setup_tesseract_path

    if OCR_AVAILABLE:
        import io

        import pytesseract
        from PIL import Image
except ImportError:
    OCR_AVAILABLE = False

    def get_ocr_status():
        return {"ocr_enabled": False}

    logger.warning("OCR dependencies not available. OCR support disabled.")


@dataclass
class PageContent:
    """Represents content from a single PDF page"""

    page_num: int
    text: str
    char_count: int
    word_count: int
    line_count: int
    tables: List[Dict] = None
    images: List[Dict] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PDFDocument:
    """Represents a processed PDF document"""

    file_path: str
    file_name: str
    title: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    keywords: Optional[str]
    creator: Optional[str]
    producer: Optional[str]
    creation_date: Optional[str]
    modification_date: Optional[str]
    num_pages: int
    total_chars: int
    total_words: int
    pages: List[PageContent]
    processing_timestamp: str
    source_format: str = "vector"  # "vector", "scan", or "mixed"

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["pages"] = [page.to_dict() for page in self.pages]
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class PDFProcessor:
    """
    PDF processing class for extracting text and metadata
    """

    def __init__(
        self,
        extract_tables: bool = False,
        extract_images: bool = False,
        min_text_length: int = 10,
        enable_ocr: bool = False,
        ocr_language: str = "eng",
        ocr_cache_dir: Optional[Path] = None,
        ocr_min_confidence: float = 30.0,
    ):
        """
        Initialize PDF processor

        Args:
            extract_tables: Whether to extract table data
            extract_images: Whether to extract image metadata
            min_text_length: Minimum text length to consider a page valid
            enable_ocr: Whether to enable OCR for scanned pages
            ocr_language: Language for OCR (default: 'eng')
            ocr_cache_dir: Directory to cache OCR results
            ocr_min_confidence: Minimum OCR confidence to accept text
        """
        self.extract_tables = extract_tables
        self.extract_images = extract_images
        self.min_text_length = min_text_length
        self.enable_ocr = enable_ocr and OCR_AVAILABLE
        self.ocr_language = ocr_language
        self.ocr_min_confidence = ocr_min_confidence

        # Setup OCR cache directory
        if ocr_cache_dir:
            self.ocr_cache_dir = Path(ocr_cache_dir)
        else:
            self.ocr_cache_dir = Path("data/staging/ocr_cache")

        if self.enable_ocr:
            self.ocr_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"OCR enabled with cache at: {self.ocr_cache_dir}")

    def process_pdf(self, pdf_path: Path) -> PDFDocument:
        """
        Process a PDF file and extract content

        Args:
            pdf_path: Path to the PDF file

        Returns:
            PDFDocument with extracted content and metadata
        """
        logger.info(f"Processing PDF: {pdf_path}")

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            doc = fitz.open(str(pdf_path))

            # Extract metadata
            metadata = doc.metadata

            # Process each page
            pages = []
            total_chars = 0
            total_words = 0
            scanned_pages = 0
            vector_pages = 0

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_content, is_ocr = self._process_page_with_ocr(
                    page, page_num + 1, str(pdf_path)
                )

                if page_content.char_count >= self.min_text_length:
                    pages.append(page_content)
                    total_chars += page_content.char_count
                    total_words += page_content.word_count
                    if is_ocr:
                        scanned_pages += 1
                    else:
                        vector_pages += 1
                else:
                    logger.debug(f"Skipping page {page_num + 1} - insufficient text")

            # Determine source format
            if scanned_pages == 0:
                source_format = "vector"
            elif vector_pages == 0:
                source_format = "scan"
            else:
                source_format = "mixed"

            doc.close()

            # Create PDFDocument
            pdf_doc = PDFDocument(
                file_path=str(pdf_path),
                file_name=pdf_path.name,
                title=metadata.get("title"),
                author=metadata.get("author"),
                subject=metadata.get("subject"),
                keywords=metadata.get("keywords"),
                creator=metadata.get("creator"),
                producer=metadata.get("producer"),
                creation_date=self._format_date(metadata.get("creationDate")),
                modification_date=self._format_date(metadata.get("modDate")),
                num_pages=len(pages),
                total_chars=total_chars,
                total_words=total_words,
                pages=pages,
                processing_timestamp=datetime.now().isoformat(),
                source_format=source_format,
            )

            logger.info(
                f"Successfully processed {pdf_path.name}: "
                f"{len(pages)} pages, {total_words} words, "
                f"format: {source_format}"
            )

            return pdf_doc

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            raise

    def _process_page_with_ocr(
        self, page, page_num: int, pdf_path: str
    ) -> Tuple[PageContent, bool]:
        """Process a page with OCR fallback if needed"""
        # First try normal text extraction
        page_content = self._process_page(page, page_num)

        # Check if we need OCR (text too short)
        if self.enable_ocr and page_content.char_count < 40:
            logger.debug(
                f"Page {page_num} has insufficient text ({page_content.char_count} chars), attempting OCR"
            )

            # Try to get from cache first
            cache_key = self._get_ocr_cache_key(pdf_path, page_num)
            cached_text = self._get_cached_ocr(cache_key)

            if cached_text is not None:
                logger.debug(f"Using cached OCR for page {page_num}")
                ocr_text = cached_text
            else:
                # Perform OCR
                ocr_text = self._perform_ocr(page)
                if ocr_text:
                    # Cache the result
                    self._cache_ocr_result(cache_key, ocr_text)

            if ocr_text and len(ocr_text) > page_content.char_count:
                # OCR produced more text, use it instead
                logger.info(f"OCR extracted {len(ocr_text)} chars from page {page_num}")

                # Create new PageContent with OCR text
                page_content = PageContent(
                    page_num=page_num,
                    text=ocr_text,
                    char_count=len(ocr_text),
                    word_count=len(ocr_text.split()),
                    line_count=len(ocr_text.splitlines()),
                    tables=page_content.tables,
                    images=page_content.images,
                )
                return page_content, True  # True indicates OCR was used

        return page_content, False  # False indicates vector text was used

    def _process_page(self, page, page_num: int) -> PageContent:
        """Process a single PDF page"""
        # Extract text
        text = page.get_text()

        # Clean text
        text = self._clean_text(text)

        # Calculate metrics
        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.splitlines())

        # Extract tables if requested
        tables = None
        if self.extract_tables:
            tables = self._extract_tables(page)

        # Extract images if requested
        images = None
        if self.extract_images:
            images = self._extract_images(page)

        return PageContent(
            page_num=page_num,
            text=text,
            char_count=char_count,
            word_count=word_count,
            line_count=line_count,
            tables=tables,
            images=images,
        )

    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove excessive whitespace
        lines = text.splitlines()
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)

        # Join with single newlines
        text = "\n".join(cleaned_lines)

        # Replace multiple spaces with single space
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)

        return text.strip()

    def _perform_ocr(self, page) -> Optional[str]:
        """Perform OCR on a PDF page"""
        if not self.enable_ocr:
            return None

        try:
            # Render page to image
            mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.pil_tobytes(format="PNG")
            image = Image.open(io.BytesIO(img_data))

            # Perform OCR
            logger.debug(f"Performing OCR on page {page.number + 1}")
            ocr_data = pytesseract.image_to_data(
                image, lang=self.ocr_language, output_type=pytesseract.Output.DICT
            )

            # Extract text with confidence filtering
            text_parts = []
            for i, conf in enumerate(ocr_data["conf"]):
                if float(conf) > self.ocr_min_confidence:
                    text = ocr_data["text"][i]
                    if text and text.strip():
                        text_parts.append(text)

            # Join text parts
            ocr_text = " ".join(text_parts)

            # Post-process OCR text
            ocr_text = self._post_process_ocr_text(ocr_text)

            return ocr_text if ocr_text else None

        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return None

    def _post_process_ocr_text(self, text: str) -> str:
        """Post-process OCR text to improve quality"""
        if not text:
            return text

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Fix common OCR errors
        replacements = {
            r"\bl\b": "I",  # Standalone 'l' often should be 'I'
            r"\bO\b": "0",  # Standalone 'O' in numbers
            r"[\u2018\u2019]": "'",  # Smart quotes to regular
            r"[\u201C\u201D]": '"',
            r"\s+([.,;!?])": r"\1",  # Remove space before punctuation
            r"([.,;!?])(\w)": r"\1 \2",  # Add space after punctuation
        }

        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)

        # Normalize unicode
        text = unicodedata.normalize("NFKD", text)

        # Merge hyphenated words at line breaks
        text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)

        return text.strip()

    def _get_ocr_cache_key(self, pdf_path: str, page_num: int) -> str:
        """Generate a cache key for OCR results"""
        # Create a unique key based on file path and page
        key_string = f"{pdf_path}:{page_num}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cached_ocr(self, cache_key: str) -> Optional[str]:
        """Retrieve cached OCR result"""
        if not self.enable_ocr:
            return None

        cache_file = self.ocr_cache_dir / f"{cache_key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load OCR cache: {e}")
        return None

    def _cache_ocr_result(self, cache_key: str, text: str):
        """Cache OCR result for future use"""
        if not self.enable_ocr:
            return

        cache_file = self.ocr_cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(text, f)
        except Exception as e:
            logger.warning(f"Failed to cache OCR result: {e}")

    def _extract_tables(self, page) -> List[Dict]:
        """Extract table data from page (placeholder)"""
        # This would require more sophisticated table extraction
        # For now, return empty list
        return []

    def _extract_images(self, page) -> List[Dict]:
        """Extract image metadata from page"""
        images = []
        image_list = page.get_images()

        for img_index, img in enumerate(image_list):
            images.append(
                {"index": img_index, "xref": img[0], "width": img[2], "height": img[3]}
            )

        return images if images else None

    def _format_date(self, date_str: str) -> Optional[str]:
        """Format PDF date string"""
        if not date_str:
            return None

        # PDF dates are in format: D:YYYYMMDDHHmmSS
        if date_str.startswith("D:"):
            date_str = date_str[2:]

        try:
            # Parse and format
            year = date_str[0:4]
            month = date_str[4:6] if len(date_str) > 4 else "01"
            day = date_str[6:8] if len(date_str) > 6 else "01"
            return f"{year}-{month}-{day}"
        except:
            return date_str

    def process_directory(
        self, directory: Path, pattern: str = "*.pdf", recursive: bool = True
    ) -> List[PDFDocument]:
        """
        Process all PDFs in a directory

        Args:
            directory: Directory containing PDFs
            pattern: File pattern to match
            recursive: Whether to search recursively

        Returns:
            List of processed PDFDocuments
        """
        documents = []

        if recursive:
            pdf_files = list(directory.rglob(pattern))
        else:
            pdf_files = list(directory.glob(pattern))

        logger.info(f"Found {len(pdf_files)} PDF files to process")

        for pdf_path in pdf_files:
            try:
                doc = self.process_pdf(pdf_path)
                documents.append(doc)
            except Exception as e:
                logger.error(f"Failed to process {pdf_path}: {e}")
                continue

        logger.info(f"Successfully processed {len(documents)} documents")
        return documents

    def save_processed_documents(self, documents: List[PDFDocument], output_dir: Path):
        """Save processed documents to JSON files"""
        output_dir.mkdir(parents=True, exist_ok=True)

        for doc in documents:
            output_file = output_dir / f"{Path(doc.file_name).stem}_processed.json"

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(doc.to_json())

            logger.info(f"Saved processed document: {output_file}")


# Export main classes
__all__ = ["PDFProcessor", "PDFDocument", "PageContent"]
