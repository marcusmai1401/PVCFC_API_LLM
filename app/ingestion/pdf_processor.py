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
import torch
from loguru import logger

# Import table extraction
try:
    from .table_extractor import TableData, TableExtractor
except ImportError:
    TableExtractor = None
    TableData = None
    logger.warning("TableExtractor not available. Table extraction disabled.")

# Import Google Cloud Vision API for OCR (replaces PaddleOCR)
try:
    from google.cloud import vision

    OCR_AVAILABLE = True
    logger.info("✓ Google Cloud Vision API available")
except ImportError as e:
    OCR_AVAILABLE = False
    logger.warning(f"Google Cloud Vision API not available: {e}. OCR support disabled.")


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
        table_min_rows: int = 2,
        table_min_cols: int = 2,
        document_type: Optional[str] = None,
    ):
        """
        Initialize PDF processor

        Args:
            extract_tables: Whether to extract table data
            extract_images: Whether to extract image metadata
            min_text_length: Minimum text length to consider a page valid
            enable_ocr: Whether to enable OCR for scanned pages (Google Cloud Vision)
            table_min_rows: Minimum rows for valid table (default: 2)
            table_min_cols: Minimum columns for valid table (default: 2)
            document_type: Document type for OCR threshold determination ('CAD-like' or 'non-CAD-like')
        """
        self.extract_tables = extract_tables
        self.extract_images = extract_images
        self.min_text_length = min_text_length
        self.enable_ocr = enable_ocr and OCR_AVAILABLE
        self.document_type = document_type

        # Initialize table extractor if enabled
        self.table_extractor = None
        if self.extract_tables and TableExtractor is not None:
            self.table_extractor = TableExtractor(
                min_rows=table_min_rows,
                min_cols=table_min_cols,
            )
            logger.info(
                f"Table extraction enabled: min_rows={table_min_rows}, min_cols={table_min_cols}"
            )
        elif self.extract_tables and TableExtractor is None:
            logger.warning(
                "Table extraction requested but TableExtractor not available"
            )

        if self.enable_ocr:
            logger.info("OCR enabled (Google Cloud Vision API)")

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
                try:
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
                        logger.debug(
                            f"Skipping page {page_num + 1} - insufficient text"
                        )
                except RecursionError as e:
                    logger.error(
                        f"Recursion limit exceeded processing page {page_num + 1}. "
                        f"Skipping this page. This may be caused by complex PDF structures (deeply nested tables/annotations)."
                    )
                    # Continue processing other pages
                    continue
                except Exception as e:
                    logger.warning(f"Error processing page {page_num + 1}: {e}")
                    # Continue processing other pages
                    continue

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
        """Process a page with OCR fallback if needed

        OCR Threshold Logic:
        - CAD-like documents: char_count < 1700 → OCR enabled
        - Non-CAD-like documents: char_count < 40 → OCR enabled
        """
        # First try normal text extraction
        page_content = self._process_page(page, page_num)

        # Determine OCR threshold based on document type
        if self.document_type == "CAD-like":
            # CAD-like: Higher threshold to catch graphics text
            OCR_CHAR_THRESHOLD = 1700
            logger.debug(f"Page {page_num}: Using CAD-like OCR threshold (1700 chars)")
        else:
            # Regular technical docs: Increased threshold to capture headers/footers/partial scans
            OCR_CHAR_THRESHOLD = 100
            logger.debug(
                f"Page {page_num}: Using regular doc OCR threshold (100 chars)"
            )

        should_ocr = self.enable_ocr and page_content.char_count < OCR_CHAR_THRESHOLD

        if should_ocr:
            logger.debug(
                f"Page {page_num} has insufficient text ({page_content.char_count} chars < {OCR_CHAR_THRESHOLD}), attempting OCR"
            )

            # Perform OCR with Google Cloud Vision (returns response object)
            ocr_response = self._perform_ocr(page)

            if ocr_response and ocr_response.text_annotations:
                # Extract text from first annotation (full text)
                ocr_text = ocr_response.text_annotations[0].description.strip()

                # NEW: Geometric Assembly for P&ID tags (for CAD-like documents)
                assembled_tags_text = ""
                if self.document_type == "CAD-like":
                    try:
                        from .geometric_assembly import GeometricAssembler

                        assembler = GeometricAssembler(
                            vertical_tolerance=0.3,
                            horizontal_tolerance=0.2,
                            min_confidence=0.5,
                        )

                        assembled_tags = assembler.extract_tags_from_vision_response(
                            ocr_response
                        )

                        if assembled_tags:
                            tag_strings = [tag.tag for tag in assembled_tags]
                            assembled_tags_text = "\n".join(tag_strings)
                            logger.info(
                                f"Page {page_num}: Assembled {len(assembled_tags)} P&ID tags"
                            )
                            logger.debug(
                                f"Tags: {', '.join(tag_strings[:5])}{'...' if len(tag_strings) > 5 else ''}"
                            )

                    except Exception as e:
                        logger.warning(f"Geometric assembly failed: {e}")

                # Use OCR text if it produced more text than vector extraction
                if len(ocr_text) > page_content.char_count:
                    # Use OCR + assembled tags
                    final_text = ocr_text
                    if assembled_tags_text:
                        final_text = (
                            f"{ocr_text}\n\n[Assembled Tags]\n{assembled_tags_text}"
                        )

                    logger.info(
                        f"OCR extracted {len(ocr_text)} chars from page {page_num}"
                    )

                    page_content = PageContent(
                        page_num=page_num,
                        text=final_text,
                        char_count=len(final_text),
                        word_count=len(final_text.split()),
                        line_count=len(final_text.splitlines()),
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
            tables = self._extract_tables(page, page_num)

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
                # Collapse multiple spaces within the line
                line = re.sub(r"[ \t]+", " ", line)
                cleaned_lines.append(line)

        # Join with single newlines
        text = "\n".join(cleaned_lines)

        # Restore paragraph breaks (double newline) where appropriate
        # This heuristic is tricky; simple single newlines are safer for tables
        # text = re.sub(r"\n\s*\n", "\n\n", text)

        return text.strip()

    def _enhance_image_realesrgan(self, img_bytes: bytes) -> bytes:
        """
        Enhance image using Real-ESRGAN 2x upscaling

        Args:
            img_bytes: Original PNG image bytes

        Returns:
            Enhanced PNG image bytes (2x resolution)
        """
        try:
            import cv2
            import numpy as np
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer

            # Initialize model (lazy loading, cached after first use)
            if not hasattr(self, "_esrgan_model"):
                logger.info("Loading Real-ESRGAN model (first time only)...")
                model = RRDBNet(
                    num_in_ch=3,
                    num_out_ch=3,
                    num_feat=64,
                    num_block=6,
                    num_grow_ch=32,
                    scale=4,
                )

                model_path = (
                    Path(__file__).parent.parent.parent
                    / "RealESRGAN_x4plus_anime_6B.pth"
                )

                if not model_path.exists():
                    logger.error(f"Real-ESRGAN model not found at: {model_path}")
                    return img_bytes

                device = "cuda" if torch.cuda.is_available() else "cpu"

                self._esrgan_model = RealESRGANer(
                    scale=4,
                    model_path=str(model_path),
                    model=model,
                    tile=400,  # Process in tiles to avoid OOM
                    tile_pad=10,
                    pre_pad=0,
                    half=True if device == "cuda" else False,  # Use FP16 on GPU only
                    device=device,
                )
                logger.info(f"Real-ESRGAN loaded on {device}")

            # Decode image
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                logger.warning("Failed to decode image for enhancement")
                return img_bytes

            # Check image size before enhancement to avoid OOM
            height, width = img.shape[:2]
            pixels = height * width
            # Estimate memory: (h * w * 3 channels * 4 bytes/float32) * 2x upscale = h*w*12*4
            estimated_mem_gb = (pixels * 3 * 4 * 4) / (
                1024**3
            )  # 4x for 2x upscale each dimension

            if estimated_mem_gb > 1.0:
                logger.warning(
                    f"Image too large for Real-ESRGAN: {width}x{height} "
                    f"(estimated {estimated_mem_gb:.2f} GB memory needed, limit 1.0 GB). "
                    f"Skipping enhancement."
                )
                return img_bytes

            # Enhance (2x upscale only to keep size manageable for Vision API)
            orig_size = f"{img.shape[1]}x{img.shape[0]}"
            logger.debug(f"Enhancing image: {orig_size} -> 2x")
            enhanced, _ = self._esrgan_model.enhance(img, outscale=2)

            # Encode back to PNG
            _, buffer = cv2.imencode(".png", enhanced)
            enhanced_bytes = buffer.tobytes()

            logger.debug(
                f"Enhanced: {len(img_bytes)//1024}KB -> {len(enhanced_bytes)//1024}KB"
            )
            return enhanced_bytes

        except Exception as e:
            logger.warning(f"Real-ESRGAN enhancement failed: {e}")
            logger.exception(e)
            return img_bytes  # Fallback to original

    def _perform_ocr(self, page):
        """Perform OCR on a PDF page using Google Cloud Vision API with Real-ESRGAN enhancement

        Returns:
            Vision API response object (contains text_annotations with bounding boxes) or None
        """
        if not self.enable_ocr:
            return None

        try:
            # Initialize Vision API client
            client = vision.ImageAnnotatorClient()

            # Render page to image with high resolution for better OCR
            page_width = page.rect.width
            page_height = page.rect.height

            # Determine zoom factor based on page size
            if page_width < 600 or page_height < 800:
                zoom = 3  # ~216 DPI for small pages
                logger.debug(
                    f"Using 3x zoom for small page ({page_width:.0f}x{page_height:.0f} pts)"
                )
            elif page_width > 1200 or page_height > 1600:
                zoom = 2  # ~144 DPI for large pages
            else:
                zoom = 2.5  # ~180 DPI for medium pages

            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PNG bytes
            img_bytes = pix.pil_tobytes(format="PNG")

            # Calculate effective DPI of rendered image
            page_width_pts = page.rect.width
            page_height_pts = page.rect.height
            pixmap_width_px = pix.width
            pixmap_height_px = pix.height

            # Effective DPI = (pixels / points) * 72 (pts per inch)
            effective_dpi_x = (pixmap_width_px / page_width_pts) * 72
            effective_dpi_y = (pixmap_height_px / page_height_pts) * 72
            effective_dpi = min(effective_dpi_x, effective_dpi_y)

            logger.debug(
                f"Page rendered at {effective_dpi:.1f} DPI "
                f"({pixmap_width_px}x{pixmap_height_px} px from {page_width_pts:.0f}x{page_height_pts:.0f} pts)"
            )

            # ✨ Apply Real-ESRGAN if:
            # 1. CAD-like document (from CADLikeGate)
            # 2. OR very low DPI (< 120) regardless of document type
            should_enhance = self.document_type == "CAD-like" or effective_dpi < 120

            if should_enhance:
                if effective_dpi < 120:
                    logger.info(
                        f"Low DPI detected ({effective_dpi:.1f} < 120), applying Real-ESRGAN"
                    )
                else:
                    logger.debug(
                        f"Applying Real-ESRGAN for {self.document_type} document"
                    )
                enhanced_bytes = self._enhance_image_realesrgan(img_bytes)
            else:
                enhanced_bytes = img_bytes
                logger.debug(
                    f"Skipped Real-ESRGAN (DPI={effective_dpi:.1f}, type={self.document_type})"
                )

            # Check payload size limit (Google Vision API: ~40MB)
            payload_size_mb = len(enhanced_bytes) / (1024 * 1024)
            MAX_PAYLOAD_MB = 38  # Safety margin below 40MB limit

            if payload_size_mb > MAX_PAYLOAD_MB:
                logger.warning(
                    f"Payload too large: {payload_size_mb:.2f} MB > {MAX_PAYLOAD_MB} MB. "
                    f"Compressing with JPEG quality=85..."
                )

                # Re-encode with JPEG compression
                import cv2
                import numpy as np

                nparr = np.frombuffer(enhanced_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img is not None:
                    _, buffer = cv2.imencode(
                        ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85]
                    )
                    enhanced_bytes = buffer.tobytes()
                    logger.info(
                        f"Compressed: {payload_size_mb:.2f} MB -> {len(enhanced_bytes)/(1024*1024):.2f} MB"
                    )
                else:
                    logger.error("Failed to compress image, skipping OCR for this page")
                    return None

            # Prepare Vision API request with enhanced (or original) image
            image = vision.Image(content=enhanced_bytes)

            # Perform OCR with Google Cloud Vision
            logger.debug(f"Performing OCR on enhanced image (page {page.number + 1})")
            response = client.text_detection(image=image)

            if response.error.message:
                logger.error(f"Vision API error: {response.error.message}")
                return None

            # Return full response object (contains text_annotations with bounding boxes)
            return response

        except Exception as e:
            logger.warning(f"Google Cloud Vision OCR failed: {e}")
            logger.exception(e)
            return None

    def _extract_tables(self, page, page_num: int) -> List[Dict]:
        """Extract table data from page using TableExtractor"""
        if not self.table_extractor:
            return []

        try:
            # Extract tables using TableExtractor
            table_data_list = self.table_extractor.extract_tables_from_page(
                page, page_num
            )

            # Convert TableData objects to dictionaries
            tables = [table.to_dict() for table in table_data_list]

            if tables:
                logger.debug(f"Extracted {len(tables)} table(s) from page {page_num}")

            return tables if tables else []

        except RecursionError as e:
            logger.warning(
                f"Recursion limit exceeded extracting tables from page {page_num}. "
                f"Skipping table extraction for this page. Consider simpler PDF structure."
            )
            return []
        except Exception as e:
            logger.warning(f"Failed to extract tables from page {page_num}: {e}")
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
