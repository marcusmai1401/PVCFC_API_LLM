"""
PDF Page Rendering Module

Provides functionality to render PDF pages as images with caching support.
Uses PyMuPDF (fitz) for PDF processing and Pillow for image manipulation.
"""

import hashlib
import io
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    import pymupdf as fitz

from cachetools import LRUCache, TTLCache
from loguru import logger
from PIL import Image

# Configuration
DEFAULT_DPI = 150
DEFAULT_FORMAT = "png"
CACHE_DIR = Path("artifacts/cache/pdf_pages")
CACHE_TTL_HOURS = 24
MAX_MEMORY_CACHE_SIZE = 100  # Maximum number of images in memory
MAX_DPI = 300
MIN_DPI = 72

# Supported image formats
SUPPORTED_FORMATS = {"png", "jpeg", "jpg", "webp"}

# In-memory cache for frequently accessed images
memory_cache = TTLCache(maxsize=MAX_MEMORY_CACHE_SIZE, ttl=CACHE_TTL_HOURS * 3600)

# BBox cache configuration
MAX_BBOX_CACHE_SIZE = 500  # Maximum number of bbox results in cache
BBOX_CACHE_TTL_HOURS = 12  # Shorter TTL for bbox cache
bbox_cache = TTLCache(maxsize=MAX_BBOX_CACHE_SIZE, ttl=BBOX_CACHE_TTL_HOURS * 3600)


class PDFRenderer:
    """Main PDF rendering class with caching support."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize PDF renderer with optional custom cache directory."""
        self.cache_dir = cache_dir or CACHE_DIR
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cache directory initialized: {self.cache_dir}")

    def _get_pdf_hash(self, pdf_path: Path) -> str:
        """Generate hash for PDF file based on path and modification time."""
        stat = pdf_path.stat()
        hash_input = f"{pdf_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def _get_cache_key(
        self, pdf_path: Path, page_num: int, dpi: int, format: str
    ) -> str:
        """Generate cache key for rendered page."""
        pdf_hash = self._get_pdf_hash(pdf_path)
        return f"{pdf_hash}_{page_num}_{dpi}_{format}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cached image."""
        # Use subdirectories to avoid too many files in one directory
        subdir = cache_key[:2]
        return self.cache_dir / subdir / f"{cache_key}.cache"

    def _save_to_cache(
        self, cache_key: str, image_data: bytes, metadata: Dict[str, Any]
    ):
        """Save rendered image to cache."""
        try:
            # Save to memory cache
            memory_cache[cache_key] = {
                "data": image_data,
                "metadata": metadata,
                "timestamp": datetime.now(),
            }

            # Save to file cache
            cache_path = self._get_cache_path(cache_key)
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Save image data
            with open(cache_path, "wb") as f:
                f.write(image_data)

            # Save metadata
            meta_path = cache_path.with_suffix(".meta")
            with open(meta_path, "w") as f:
                json.dump(metadata, f)

            logger.debug(f"Cached image: {cache_key}")

        except Exception as e:
            logger.warning(f"Failed to cache image: {e}")

    def _load_from_cache(
        self, cache_key: str
    ) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """Load rendered image from cache."""
        try:
            # Check memory cache first
            if cache_key in memory_cache:
                cached = memory_cache[cache_key]
                logger.debug(f"Memory cache hit: {cache_key}")
                return cached["data"], cached["metadata"]

            # Check file cache
            cache_path = self._get_cache_path(cache_key)
            if cache_path.exists():
                meta_path = cache_path.with_suffix(".meta")

                # Check if metadata exists and is valid
                if meta_path.exists():
                    with open(meta_path, "r") as f:
                        metadata = json.load(f)

                    # Check TTL
                    cached_time = datetime.fromisoformat(metadata.get("timestamp", ""))
                    if datetime.now() - cached_time < timedelta(hours=CACHE_TTL_HOURS):
                        with open(cache_path, "rb") as f:
                            image_data = f.read()

                        # Add to memory cache for faster access
                        memory_cache[cache_key] = {
                            "data": image_data,
                            "metadata": metadata,
                            "timestamp": cached_time,
                        }

                        logger.debug(f"File cache hit: {cache_key}")
                        return image_data, metadata

        except Exception as e:
            logger.warning(f"Failed to load from cache: {e}")

        return None

    def validate_pdf_path(self, pdf_path: str) -> Tuple[bool, str]:
        """
        Validate PDF file path.

        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(pdf_path)

        if not path.exists():
            return False, f"PDF file not found: {pdf_path}"

        if not path.is_file():
            return False, f"Path is not a file: {pdf_path}"

        if path.suffix.lower() not in [".pdf"]:
            return False, f"File is not a PDF: {pdf_path}"

        try:
            # Try to open the PDF to validate it's not corrupted
            with fitz.open(path) as doc:
                _ = doc.page_count
            return True, ""
        except Exception as e:
            return False, f"Invalid or corrupted PDF: {e}"

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """Get total number of pages in PDF."""
        is_valid, error_msg = self.validate_pdf_path(pdf_path)
        if not is_valid:
            raise ValueError(error_msg)

        with fitz.open(pdf_path) as doc:
            return doc.page_count

    def render_page_to_image(
        self,
        pdf_path: str,
        page_num: int,
        dpi: int = DEFAULT_DPI,
        format: str = DEFAULT_FORMAT,
        use_cache: bool = True,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Render a specific PDF page to image.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)
            dpi: Resolution in DPI
            format: Output image format
            use_cache: Whether to use caching

        Returns:
            Tuple of (image_data, metadata)
        """
        # Validate inputs
        is_valid, error_msg = self.validate_pdf_path(pdf_path)
        if not is_valid:
            raise ValueError(error_msg)

        if format.lower() not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {format}. Supported: {SUPPORTED_FORMATS}"
            )

        if not MIN_DPI <= dpi <= MAX_DPI:
            raise ValueError(f"DPI must be between {MIN_DPI} and {MAX_DPI}")

        path = Path(pdf_path)

        # Check cache if enabled
        if use_cache:
            cache_key = self._get_cache_key(path, page_num, dpi, format.lower())
            cached = self._load_from_cache(cache_key)
            if cached:
                return cached

        # Render the page
        try:
            with fitz.open(pdf_path) as doc:
                if page_num < 1 or page_num > doc.page_count:
                    raise ValueError(
                        f"Page {page_num} out of range. PDF has {doc.page_count} pages"
                    )

                # PyMuPDF uses 0-indexed pages
                page = doc[page_num - 1]

                # Calculate zoom factor from DPI (default PDF DPI is 72)
                zoom = dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)

                # Render page to pixmap
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Convert to requested format
                output = io.BytesIO()
                save_format = (
                    "JPEG" if format.lower() in ["jpg", "jpeg"] else format.upper()
                )

                if save_format == "JPEG":
                    img.save(output, format=save_format, quality=85, optimize=True)
                else:
                    img.save(output, format=save_format)

                image_data = output.getvalue()

                # Prepare metadata
                metadata = {
                    "pdf_path": str(path),
                    "page_num": page_num,
                    "total_pages": doc.page_count,
                    "dpi": dpi,
                    "format": format.lower(),
                    "width": pix.width,
                    "height": pix.height,
                    "size_bytes": len(image_data),
                    "timestamp": datetime.now().isoformat(),
                }

                # Cache the result if enabled
                if use_cache:
                    self._save_to_cache(cache_key, image_data, metadata)

                logger.info(f"Rendered page {page_num} of {pdf_path} at {dpi} DPI")
                return image_data, metadata

        except Exception as e:
            logger.error(f"Failed to render page: {e}")
            raise

    def render_page_range(
        self,
        pdf_path: str,
        start_page: int,
        end_page: int,
        dpi: int = DEFAULT_DPI,
        format: str = DEFAULT_FORMAT,
        use_cache: bool = True,
    ) -> List[Tuple[bytes, Dict[str, Any]]]:
        """
        Render a range of PDF pages.

        Returns:
            List of (image_data, metadata) tuples
        """
        # Validate PDF
        page_count = self.get_pdf_page_count(pdf_path)

        if start_page < 1 or end_page > page_count or start_page > end_page:
            raise ValueError(
                f"Invalid page range {start_page}-{end_page}. PDF has {page_count} pages"
            )

        results = []
        for page_num in range(start_page, end_page + 1):
            result = self.render_page_to_image(
                pdf_path, page_num, dpi, format, use_cache
            )
            results.append(result)

        return results

    def get_page_thumbnail(
        self,
        pdf_path: str,
        page_num: int,
        max_width: int = 200,
        max_height: int = 200,
        format: str = "jpeg",
        use_cache: bool = True,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Generate a thumbnail for a PDF page.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)
            max_width: Maximum thumbnail width
            max_height: Maximum thumbnail height
            format: Output image format
            use_cache: Whether to use caching

        Returns:
            Tuple of (image_data, metadata)
        """
        # Calculate appropriate DPI for thumbnail
        # Start with a lower DPI for thumbnails
        thumbnail_dpi = 72

        # Render at low DPI
        image_data, metadata = self.render_page_to_image(
            pdf_path, page_num, thumbnail_dpi, "png", use_cache=False
        )

        # Load image and create thumbnail
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Save thumbnail
        output = io.BytesIO()
        save_format = "JPEG" if format.lower() in ["jpg", "jpeg"] else format.upper()

        if save_format == "JPEG":
            img.save(output, format=save_format, quality=75, optimize=True)
        else:
            img.save(output, format=save_format)

        thumb_data = output.getvalue()

        # Update metadata
        metadata["thumbnail"] = True
        metadata["max_width"] = max_width
        metadata["max_height"] = max_height
        metadata["thumb_width"] = img.width
        metadata["thumb_height"] = img.height
        metadata["size_bytes"] = len(thumb_data)

        return thumb_data, metadata

    def find_bbox_by_quote(
        self,
        pdf_path: str,
        page_num: int,
        quote: str,
        fuzzy: bool = True,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Find bounding box(es) for a text quote on a PDF page.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)
            quote: Text quote to search for
            fuzzy: If True, use fuzzy matching (case-insensitive, whitespace normalized)
            use_cache: Whether to use bbox cache

        Returns:
            List of bounding box dicts with keys:
            - bbox: (x0, y0, x1, y1) coordinates
            - text: matched text
            - confidence: match confidence (0.0-1.0)
            - page_width: page width for normalization
            - page_height: page height for normalization
        """
        # Check cache first
        if use_cache:
            cache_key = self._get_bbox_cache_key(pdf_path, page_num, quote, fuzzy)
            if cache_key in bbox_cache:
                logger.debug(f"BBox cache hit: {cache_key[:32]}...")
                return bbox_cache[cache_key]

        # Validate PDF
        is_valid, error_msg = self.validate_pdf_path(pdf_path)
        if not is_valid:
            raise ValueError(error_msg)

        results = []

        try:
            with fitz.open(pdf_path) as doc:
                if page_num < 1 or page_num > doc.page_count:
                    raise ValueError(
                        f"Page {page_num} out of range. PDF has {doc.page_count} pages"
                    )

                page = doc[page_num - 1]
                page_width = page.rect.width
                page_height = page.rect.height

                # Normalize quote for matching
                quote_normalized = (
                    self._normalize_text_for_bbox(quote) if fuzzy else quote
                )

                # Method 1: Try exact search first (PyMuPDF's search_for)
                if not fuzzy:
                    # Exact search
                    text_instances = page.search_for(quote)
                    for rect in text_instances:
                        results.append(
                            {
                                "bbox": (rect.x0, rect.y0, rect.x1, rect.y1),
                                "text": quote,
                                "confidence": 1.0,
                                "page_width": page_width,
                                "page_height": page_height,
                                "method": "exact",
                            }
                        )
                else:
                    # Fuzzy search: extract all text with positions and match
                    text_dict = page.get_text("dict")
                    matches = self._fuzzy_text_search(
                        text_dict, quote_normalized, page_width, page_height
                    )
                    results.extend(matches)

                # Cache results
                if use_cache:
                    bbox_cache[cache_key] = results

                logger.info(
                    f"Found {len(results)} bbox(es) for quote '{quote[:50]}...' "
                    f"on page {page_num} of {pdf_path}"
                )

        except Exception as e:
            logger.error(f"Failed to find bbox: {e}")
            raise

        return results

    def _get_bbox_cache_key(
        self, pdf_path: str, page_num: int, quote: str, fuzzy: bool
    ) -> str:
        """Generate cache key for bbox search."""
        path = Path(pdf_path)
        pdf_hash = self._get_pdf_hash(path)
        quote_hash = hashlib.md5(quote.encode()).hexdigest()[:16]
        fuzzy_flag = "fuzzy" if fuzzy else "exact"
        return f"{pdf_hash}_{page_num}_{quote_hash}_{fuzzy_flag}"

    def _normalize_text_for_bbox(self, text: str) -> str:
        """Normalize text for fuzzy bbox matching."""
        import re

        # Lowercase
        text = text.lower()
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove punctuation (but keep important ones)
        text = re.sub(r"[^\w\s.,;:!?-]", "", text)
        return text.strip()

    def _fuzzy_text_search(
        self,
        text_dict: Dict,
        quote_normalized: str,
        page_width: float,
        page_height: float,
    ) -> List[Dict[str, Any]]:
        """
        Perform fuzzy text search in page text dictionary.

        Args:
            text_dict: PyMuPDF text dictionary
            quote_normalized: Normalized search quote
            page_width: Page width
            page_height: Page height

        Returns:
            List of bbox matches
        """
        from difflib import SequenceMatcher

        matches = []
        quote_words = quote_normalized.split()

        if not quote_words:
            return matches

        # Extract all text blocks with positions
        text_blocks = []
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    line_text_parts = []
                    line_bbox = None

                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        span_bbox = span.get("bbox", (0, 0, 0, 0))

                        if span_text.strip():
                            line_text_parts.append(span_text)

                            # Expand line bbox
                            if line_bbox is None:
                                line_bbox = list(span_bbox)
                            else:
                                line_bbox[0] = min(line_bbox[0], span_bbox[0])  # x0
                                line_bbox[1] = min(line_bbox[1], span_bbox[1])  # y0
                                line_bbox[2] = max(line_bbox[2], span_bbox[2])  # x1
                                line_bbox[3] = max(line_bbox[3], span_bbox[3])  # y1

                    if line_text_parts and line_bbox:
                        line_text = " ".join(line_text_parts)
                        text_blocks.append(
                            {
                                "text": line_text,
                                "bbox": tuple(line_bbox),
                            }
                        )

        # Search for quote in text blocks
        for i, block in enumerate(text_blocks):
            block_text_norm = self._normalize_text_for_bbox(block["text"])

            # Check if quote is in this block
            if quote_normalized in block_text_norm:
                # Exact substring match
                matches.append(
                    {
                        "bbox": block["bbox"],
                        "text": block["text"],
                        "confidence": 1.0,
                        "page_width": page_width,
                        "page_height": page_height,
                        "method": "fuzzy_exact",
                    }
                )
            else:
                # Try fuzzy matching with SequenceMatcher
                similarity = SequenceMatcher(
                    None, quote_normalized, block_text_norm
                ).ratio()

                if similarity > 0.8:  # High similarity threshold
                    matches.append(
                        {
                            "bbox": block["bbox"],
                            "text": block["text"],
                            "confidence": similarity,
                            "page_width": page_width,
                            "page_height": page_height,
                            "method": "fuzzy_similar",
                        }
                    )

                # Also try matching across multiple consecutive blocks
                if i < len(text_blocks) - 1:
                    multi_block_text = " ".join(
                        self._normalize_text_for_bbox(text_blocks[j]["text"])
                        for j in range(i, min(i + 3, len(text_blocks)))
                    )

                    if quote_normalized in multi_block_text:
                        # Merge bboxes of consecutive blocks
                        merged_bbox = self._merge_bboxes(
                            [
                                text_blocks[j]["bbox"]
                                for j in range(i, min(i + 3, len(text_blocks)))
                            ]
                        )
                        matches.append(
                            {
                                "bbox": merged_bbox,
                                "text": " ".join(
                                    text_blocks[j]["text"]
                                    for j in range(i, min(i + 3, len(text_blocks)))
                                ),
                                "confidence": 0.95,
                                "page_width": page_width,
                                "page_height": page_height,
                                "method": "fuzzy_multi_block",
                            }
                        )

        # Sort by confidence (descending)
        matches.sort(key=lambda x: x["confidence"], reverse=True)

        # Remove duplicates (keep highest confidence)
        unique_matches = []
        seen_bboxes = set()
        for match in matches:
            bbox_tuple = match["bbox"]
            if bbox_tuple not in seen_bboxes:
                seen_bboxes.add(bbox_tuple)
                unique_matches.append(match)

        return unique_matches

    def _merge_bboxes(
        self, bboxes: List[Tuple[float, float, float, float]]
    ) -> Tuple[float, float, float, float]:
        """Merge multiple bboxes into one."""
        if not bboxes:
            return (0, 0, 0, 0)

        x0 = min(bbox[0] for bbox in bboxes)
        y0 = min(bbox[1] for bbox in bboxes)
        x1 = max(bbox[2] for bbox in bboxes)
        y1 = max(bbox[3] for bbox in bboxes)

        return (x0, y0, x1, y1)

    def extract_text_with_bbox(
        self,
        pdf_path: str,
        page_num: int,
    ) -> List[Dict[str, Any]]:
        """
        Extract all text from page with bounding boxes.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)

        Returns:
            List of text blocks with bbox info:
            - text: text content
            - bbox: (x0, y0, x1, y1) coordinates
            - page_width: page width
            - page_height: page height
        """
        is_valid, error_msg = self.validate_pdf_path(pdf_path)
        if not is_valid:
            raise ValueError(error_msg)

        results = []

        try:
            with fitz.open(pdf_path) as doc:
                if page_num < 1 or page_num > doc.page_count:
                    raise ValueError(
                        f"Page {page_num} out of range. PDF has {doc.page_count} pages"
                    )

                page = doc[page_num - 1]
                page_width = page.rect.width
                page_height = page.rect.height

                # Get text with details
                text_dict = page.get_text("dict")

                for block in text_dict.get("blocks", []):
                    if block.get("type") == 0:  # Text block
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                bbox = span.get("bbox", (0, 0, 0, 0))

                                if text.strip():
                                    results.append(
                                        {
                                            "text": text,
                                            "bbox": bbox,
                                            "page_width": page_width,
                                            "page_height": page_height,
                                            "font": span.get("font", ""),
                                            "size": span.get("size", 0),
                                        }
                                    )

                logger.info(
                    f"Extracted {len(results)} text blocks from page {page_num} of {pdf_path}"
                )

        except Exception as e:
            logger.error(f"Failed to extract text with bbox: {e}")
            raise

        return results

    def normalize_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        page_width: float,
        page_height: float,
    ) -> Tuple[float, float, float, float]:
        """
        Normalize bbox coordinates to 0-1 range.

        Args:
            bbox: (x0, y0, x1, y1) absolute coordinates
            page_width: Page width
            page_height: Page height

        Returns:
            Normalized bbox (x0, y0, x1, y1) in 0-1 range
        """
        x0, y0, x1, y1 = bbox

        if page_width <= 0 or page_height <= 0:
            return (0, 0, 0, 0)

        return (
            x0 / page_width,
            y0 / page_height,
            x1 / page_width,
            y1 / page_height,
        )

    def denormalize_bbox(
        self,
        normalized_bbox: Tuple[float, float, float, float],
        page_width: float,
        page_height: float,
    ) -> Tuple[float, float, float, float]:
        """
        Denormalize bbox coordinates from 0-1 range to absolute.

        Args:
            normalized_bbox: (x0, y0, x1, y1) in 0-1 range
            page_width: Page width
            page_height: Page height

        Returns:
            Absolute bbox (x0, y0, x1, y1)
        """
        x0, y0, x1, y1 = normalized_bbox

        return (
            x0 * page_width,
            y0 * page_height,
            x1 * page_width,
            y1 * page_height,
        )

    def clear_bbox_cache(self):
        """Clear bbox cache."""
        bbox_cache.clear()
        logger.info("BBox cache cleared")

    def get_bbox_cache_stats(self) -> Dict[str, Any]:
        """Get bbox cache statistics."""
        return {
            "bbox_cache_size": len(bbox_cache),
            "bbox_cache_max_size": MAX_BBOX_CACHE_SIZE,
            "bbox_cache_ttl_hours": BBOX_CACHE_TTL_HOURS,
        }

    def clear_cache(self, pdf_path: Optional[str] = None):
        """
        Clear cache for specific PDF or all cache.

        Args:
            pdf_path: If provided, only clear cache for this PDF
        """
        if pdf_path:
            path = Path(pdf_path)
            pdf_hash = self._get_pdf_hash(path)

            # Clear from memory cache
            keys_to_remove = [k for k in memory_cache.keys() if k.startswith(pdf_hash)]
            for key in keys_to_remove:
                del memory_cache[key]

            # Clear from file cache
            for cache_file in self.cache_dir.rglob(f"{pdf_hash}*"):
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete cache file {cache_file}: {e}")

            logger.info(f"Cleared cache for {pdf_path}")
        else:
            # Clear all cache
            memory_cache.clear()

            for cache_file in self.cache_dir.rglob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete cache file {cache_file}: {e}")

            for meta_file in self.cache_dir.rglob("*.meta"):
                try:
                    meta_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete meta file {meta_file}: {e}")

            logger.info("Cleared all cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        file_cache_size = sum(f.stat().st_size for f in self.cache_dir.rglob("*.cache"))
        file_cache_count = len(list(self.cache_dir.rglob("*.cache")))

        return {
            "memory_cache_size": len(memory_cache),
            "memory_cache_max_size": MAX_MEMORY_CACHE_SIZE,
            "file_cache_count": file_cache_count,
            "file_cache_size_mb": file_cache_size / (1024 * 1024),
            "cache_directory": str(self.cache_dir),
        }


# Module-level functions for convenience
_default_renderer = None


def get_default_renderer() -> PDFRenderer:
    """Get or create default renderer instance."""
    global _default_renderer
    if _default_renderer is None:
        _default_renderer = PDFRenderer()
    return _default_renderer


def render_page_to_image(
    pdf_path: str,
    page_num: int,
    dpi: int = DEFAULT_DPI,
    format: str = DEFAULT_FORMAT,
    use_cache: bool = True,
) -> Tuple[bytes, Dict[str, Any]]:
    """Convenience function to render PDF page using default renderer."""
    renderer = get_default_renderer()
    return renderer.render_page_to_image(pdf_path, page_num, dpi, format, use_cache)


def get_pdf_page_count(pdf_path: str) -> int:
    """Convenience function to get PDF page count."""
    renderer = get_default_renderer()
    return renderer.get_pdf_page_count(pdf_path)


def validate_pdf_path(pdf_path: str) -> Tuple[bool, str]:
    """Convenience function to validate PDF path."""
    renderer = get_default_renderer()
    return renderer.validate_pdf_path(pdf_path)


def get_page_thumbnail(
    pdf_path: str,
    page_num: int,
    max_width: int = 200,
    max_height: int = 200,
    format: str = "jpeg",
) -> Tuple[bytes, Dict[str, Any]]:
    """Convenience function to get page thumbnail."""
    renderer = get_default_renderer()
    return renderer.get_page_thumbnail(
        pdf_path, page_num, max_width, max_height, format
    )


def clear_cache(pdf_path: Optional[str] = None):
    """Convenience function to clear cache."""
    renderer = get_default_renderer()
    renderer.clear_cache(pdf_path)


def get_cache_stats() -> Dict[str, Any]:
    """Convenience function to get cache statistics."""
    renderer = get_default_renderer()
    return renderer.get_cache_stats()


def find_bbox_by_quote(
    pdf_path: str,
    page_num: int,
    quote: str,
    fuzzy: bool = True,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Convenience function to find bbox for text quote."""
    renderer = get_default_renderer()
    return renderer.find_bbox_by_quote(pdf_path, page_num, quote, fuzzy, use_cache)


def extract_text_with_bbox(pdf_path: str, page_num: int) -> List[Dict[str, Any]]:
    """Convenience function to extract text with bboxes."""
    renderer = get_default_renderer()
    return renderer.extract_text_with_bbox(pdf_path, page_num)


def normalize_bbox(
    bbox: Tuple[float, float, float, float],
    page_width: float,
    page_height: float,
) -> Tuple[float, float, float, float]:
    """Convenience function to normalize bbox."""
    renderer = get_default_renderer()
    return renderer.normalize_bbox(bbox, page_width, page_height)


def denormalize_bbox(
    normalized_bbox: Tuple[float, float, float, float],
    page_width: float,
    page_height: float,
) -> Tuple[float, float, float, float]:
    """Convenience function to denormalize bbox."""
    renderer = get_default_renderer()
    return renderer.denormalize_bbox(normalized_bbox, page_width, page_height)


def clear_bbox_cache():
    """Convenience function to clear bbox cache."""
    renderer = get_default_renderer()
    renderer.clear_bbox_cache()


def get_bbox_cache_stats() -> Dict[str, Any]:
    """Convenience function to get bbox cache statistics."""
    renderer = get_default_renderer()
    return renderer.get_bbox_cache_stats()


if __name__ == "__main__":
    # Example usage and testing
    import sys

    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        page = int(sys.argv[2]) if len(sys.argv) > 2 else 1

        # Validate PDF
        is_valid, error = validate_pdf_path(pdf_file)
        if not is_valid:
            print(f"Error: {error}")
            sys.exit(1)

        # Get page count
        page_count = get_pdf_page_count(pdf_file)
        print(f"PDF has {page_count} pages")

        # Render page
        print(f"Rendering page {page}...")
        image_data, metadata = render_page_to_image(pdf_file, page)
        print(
            f"Rendered image: {metadata['width']}x{metadata['height']}, {metadata['size_bytes']} bytes"
        )

        # Save to file for verification
        output_file = f"page_{page}.{metadata['format']}"
        with open(output_file, "wb") as f:
            f.write(image_data)
        print(f"Saved to {output_file}")

        # Show cache stats
        stats = get_cache_stats()
        print(f"Cache stats: {stats}")
    else:
        print("Usage: python pdf_renderer.py <pdf_file> [page_number]")
