"""
Page Layout Builder
Vector-first text span and drawing extraction with OCR fallback

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 5
"""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from loguru import logger

from app.config import get_config


@dataclass
class TextSpan:
    """Single text span with positioning and styling"""

    text: str
    bbox: List[float]  # [x0, y0, x1, y1] in page coordinates
    font_size: float
    rotation_deg: float
    span_id: int  # Unique ID within page


@dataclass
class VectorDrawing:
    """Vector drawing element (line, circle, rect, path)"""

    type: str  # "line", "circle", "rect", "path"
    coords: List[float]  # Coordinates depend on type
    color: Optional[Tuple[float, float, float]] = None  # RGB
    thickness: Optional[float] = None


@dataclass
class PageLayout:
    """Complete layout for a single page"""

    doc_id: str
    page: int  # 1-based
    page_width: float
    page_height: float
    spans: List[TextSpan]
    drawings: List[VectorDrawing]
    is_raster: bool  # True if OCR was used
    ocr_confidence: Optional[float] = None


class PageLayoutBuilder:
    """
    Extract page layout from PDF using vector-first approach

    Pipeline:
    1. Try vector text extraction (PyMuPDF)
    2. Extract vector drawings if available
    3. Fallback to OCR for raster pages
    4. Normalize coordinates and spacing
    """

    def __init__(
        self,
        enable_ocr: bool = True,
        enable_drawings: bool = True,
        enable_shape_aware: bool = False,
    ):
        """
        Initialize layout builder

        Args:
            enable_ocr: Enable OCR fallback for raster pages
            enable_ocr: Enable vector drawings extraction
            enable_shape_aware: Enable OpenCV shape detection (requires opencv-python)
        """
        self.config = get_config()
        self.enable_ocr = enable_ocr
        self.enable_drawings = enable_drawings
        self.enable_shape_aware = (
            enable_shape_aware and self.config.ENABLE_SHAPE_AWARE_ROI
        )

        if self.enable_shape_aware:
            try:
                import cv2

                self.cv2 = cv2
                logger.info("OpenCV available for shape-aware ROI")
            except ImportError:
                logger.warning("OpenCV not available, shape-aware ROI disabled")
                self.enable_shape_aware = False

    def build_layout(self, pdf_path: Path, page_num: int, doc_id: str) -> PageLayout:
        """
        Build layout for a single page

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-based)
            doc_id: Document ID

        Returns:
            PageLayout with spans and drawings
        """
        doc = fitz.open(str(pdf_path))
        page = doc[page_num - 1]  # Convert to 0-based

        # Get page dimensions (convert to float for JSON serialization)
        rect = page.rect
        page_width = float(rect.width)
        page_height = float(rect.height)

        # Extract text spans (vector-first)
        spans, is_raster, ocr_conf = self._extract_text_spans(page, page_num)

        # Normalize engineering spacing
        spans = self._normalize_spacing(spans)

        # Extract drawings
        drawings = []
        if self.enable_drawings and not is_raster:
            drawings = self._extract_drawings(page)

        doc.close()

        layout = PageLayout(
            doc_id=doc_id,
            page=page_num,
            page_width=page_width,
            page_height=page_height,
            spans=spans,
            drawings=drawings,
            is_raster=is_raster,
            ocr_confidence=ocr_conf,
        )

        return layout

    def _extract_text_spans(
        self, page: fitz.Page, page_num: int
    ) -> Tuple[List[TextSpan], bool, Optional[float]]:
        """
        Extract text spans with bbox and styling (vector-first)

        Args:
            page: PyMuPDF page object
            page_num: Page number for logging

        Returns:
            (spans, is_raster, ocr_confidence)
        """
        spans = []
        is_raster = False
        ocr_confidence = None

        # Try vector text first
        text_dict = page.get_text("dict")

        span_id = 0
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span_data in line.get("spans", []):
                        text = span_data.get("text", "").strip()
                        if not text:
                            continue

                        bbox = span_data.get("bbox", [])
                        font_size = span_data.get("size", 12.0)

                        # Estimate rotation from bbox geometry
                        rotation = self._estimate_rotation(bbox)

                        # Ensure bbox is fully serializable (convert any Point objects)
                        safe_bbox = [float(x) for x in bbox] if bbox else []
                        span = TextSpan(
                            text=text,
                            bbox=safe_bbox,
                            font_size=font_size,
                            rotation_deg=rotation,
                            span_id=span_id,
                        )
                        spans.append(span)
                        span_id += 1

        # Check if we got meaningful text
        total_text = "".join(s.text for s in spans)

        # Fallback to OCR if insufficient vector text
        if len(total_text.strip()) < 100 and self.enable_ocr:
            logger.debug(f"Page {page_num}: Insufficient vector text, trying OCR")
            spans, ocr_confidence = self._ocr_fallback(page)
            is_raster = True

        return spans, is_raster, ocr_confidence

    def _estimate_rotation(self, bbox: List[float]) -> float:
        """
        Estimate text rotation from bbox geometry

        Args:
            bbox: [x0, y0, x1, y1]

        Returns:
            Rotation in degrees (0 = horizontal)
        """
        if len(bbox) != 4:
            return 0.0

        x0, y0, x1, y1 = bbox
        width = abs(x1 - x0)
        height = abs(y1 - y0)

        # Simple heuristic: if height >> width, likely rotated 90°
        if height > width * 1.5:
            return 90.0
        else:
            return 0.0

    def _ocr_fallback(self, page: fitz.Page) -> Tuple[List[TextSpan], Optional[float]]:
        """
        OCR fallback for raster pages using PP-OCRv5

        Args:
            page: PyMuPDF page object

        Returns:
            (spans, average_confidence)
        """
        try:
            import io

            import numpy as np
            from PIL import Image

            from app.ingestion.paddle_ocr_config import get_paddleocr_instance

            # Get OCR instance
            ocr = get_paddleocr_instance()
            if ocr is None:
                logger.warning("OCR not available, returning empty spans")
                return [], None

            # Render page to image
            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            img_array = np.array(img)

            # Run OCR
            result = ocr.ocr(img_array, cls=True)

            if not result or not result[0]:
                return [], None

            spans = []
            confidences = []
            span_id = 0

            for line in result[0]:
                if not line:
                    continue

                bbox_coords, (text, confidence) = line

                # Convert bbox from image coords to page coords
                # bbox_coords is [[x0,y0], [x1,y1], [x2,y2], [x3,y3]]
                if len(bbox_coords) == 4:
                    xs = [p[0] for p in bbox_coords]
                    ys = [p[1] for p in bbox_coords]
                    bbox = [min(xs), min(ys), max(xs), max(ys)]

                    # Scale from image coords (300 DPI) to page coords (72 DPI)
                    scale_factor = 72 / 300
                    bbox = [c * scale_factor for c in bbox]

                    # Rough font size estimate from bbox height
                    font_size = (bbox[3] - bbox[1]) * 0.75

                    span = TextSpan(
                        text=text,
                        bbox=bbox,
                        font_size=font_size,
                        rotation_deg=0.0,  # OCR doesn't preserve rotation easily
                        span_id=span_id,
                    )
                    spans.append(span)
                    confidences.append(confidence)
                    span_id += 1

            avg_confidence = (
                sum(confidences) / len(confidences) if confidences else None
            )

            return spans, avg_confidence

        except Exception as e:
            logger.error(f"OCR fallback failed: {e}")
            return [], None

    def _extract_drawings(self, page: fitz.Page) -> List[VectorDrawing]:
        """
        Extract vector drawings (lines, circles, paths)

        Args:
            page: PyMuPDF page object

        Returns:
            List of VectorDrawing objects
        """
        drawings = []

        def safe_coord_list(items, start=1, end=None):
            """Convert PyMuPDF coords (may contain Point) to list of floats"""
            slice_items = items[start:end] if end else items[start:]
            result = []
            for x in slice_items:
                try:
                    result.append(float(x))
                except:
                    # If it's a Point or complex object, try to extract x,y
                    if hasattr(x, "x") and hasattr(x, "y"):
                        result.extend([float(x.x), float(x.y)])
                    else:
                        # Last resort: convert to string
                        result.append(str(x))
            return result

        try:
            raw_drawings = page.get_drawings()

            for idx, drawing in enumerate(raw_drawings):
                # Get drawing properties
                items = drawing.get("items", [])
                color_raw = drawing.get("color")
                # Convert color to tuple for JSON serialization
                color = tuple(color_raw) if color_raw else None
                width = drawing.get("width", 1.0)

                # Classify drawing type (simplified)
                if len(items) == 1:
                    item = items[0]
                    cmd = item[0]

                    if cmd == "l":  # Line
                        # item = ('l', x0, y0, x1, y1)
                        coords = safe_coord_list(item, 1, 5) if len(item) >= 5 else []
                        drawings.append(
                            VectorDrawing(
                                type="line",
                                coords=coords,
                                color=color,
                                thickness=width,
                            )
                        )
                    elif cmd == "c":  # Circle/curve
                        # For now, store as generic path
                        coords = safe_coord_list(item, 1) if len(item) > 1 else []
                        drawings.append(
                            VectorDrawing(
                                type="circle",
                                coords=coords,
                                color=color,
                                thickness=width,
                            )
                        )
                    elif cmd == "re":  # Rectangle
                        # item = ('re', x0, y0, x1, y1)
                        coords = safe_coord_list(item, 1, 5) if len(item) >= 5 else []
                        drawings.append(
                            VectorDrawing(
                                type="rect",
                                coords=coords,
                                color=color,
                                thickness=width,
                            )
                        )
                else:
                    # Complex path
                    # Store simplified representation
                    coords = []
                    for item in items[:10]:  # Limit to first 10 commands
                        item_coords = (
                            safe_coord_list(item, 1, 5)
                            if len(item) >= 5
                            else safe_coord_list(item, 1)
                        )
                        coords.extend(item_coords)

                    drawings.append(
                        VectorDrawing(
                            type="path",
                            coords=coords[:20],  # Limit coords
                            color=color,
                            thickness=width,
                        )
                    )

        except Exception as e:
            logger.debug(f"Drawing extraction failed: {e}")

        return drawings

    def _normalize_spacing(self, spans: List[TextSpan]) -> List[TextSpan]:
        """
        Normalize engineering spacing artifacts common in CAD/SHX fonts

        Examples:
        - "3.9  MPag" → "3.9 MPag" (double space → single)
        - "° C" → "°C" (remove space after degree symbol)
        - "2003" vs "2oo3" (normalize o vs 0 for voting logic)

        Args:
            spans: List of text spans

        Returns:
            Spans with normalized text
        """
        normalized_spans = []

        for span in spans:
            text = span.text

            # Fix double spaces
            text = re.sub(r"\s{2,}", " ", text)

            # Fix "° C" → "°C"
            text = re.sub(r"°\s+C\b", "°C", text)
            text = re.sub(r"°\s+F\b", "°F", text)

            # Normalize 2oo3 pattern (keep 'o' as is - voting logic token)
            # No change needed here, just be aware

            # Create new span with normalized text
            # Ensure bbox is fully converted to list of floats
            safe_bbox = [float(x) for x in span.bbox] if span.bbox else []
            normalized_span = TextSpan(
                text=text,
                bbox=safe_bbox,
                font_size=span.font_size,
                rotation_deg=span.rotation_deg,
                span_id=span.span_id,
            )
            normalized_spans.append(normalized_span)

        return normalized_spans

    def save_layout(self, layout: PageLayout, output_dir: Path):
        """
        Save page layout to JSON file

        Args:
            layout: PageLayout object
            output_dir: Output directory (typically LAYOUT_DIR)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Filename: page_{doc_id}_{page}.json
        filename = f"page_{layout.doc_id}_{layout.page}.json"
        output_path = output_dir / filename

        # Deep conversion to ensure all PyMuPDF objects are serializable
        def deep_serialize(obj):
            """Recursively convert all non-serializable objects"""
            if obj is None:
                return None
            elif isinstance(obj, (str, int, bool)):
                return obj
            elif isinstance(obj, float):
                return float(obj)  # Ensure it's Python float, not numpy/fitz
            elif isinstance(obj, dict):
                return {k: deep_serialize(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [deep_serialize(item) for item in obj]
            else:
                # Try to convert to float/list, fallback to string
                try:
                    return float(obj)
                except:
                    try:
                        return list(obj)
                    except:
                        return str(obj)

        # Manually serialize everything to avoid asdict with Point objects
        layout_dict = {
            "doc_id": layout.doc_id,
            "page": layout.page,
            "page_width": deep_serialize(layout.page_width),
            "page_height": deep_serialize(layout.page_height),
            "is_raster": layout.is_raster,
            "ocr_confidence": layout.ocr_confidence,
            "spans": [
                {
                    "text": s.text,
                    "bbox": deep_serialize(s.bbox),
                    "font_size": deep_serialize(s.font_size),
                    "rotation_deg": deep_serialize(s.rotation_deg),
                    "span_id": s.span_id,
                }
                for s in layout.spans
            ],
            "drawings": [
                {
                    "type": d.type,
                    "coords": deep_serialize(d.coords),
                    "color": deep_serialize(d.color),
                    "thickness": deep_serialize(d.thickness),
                }
                for d in layout.drawings
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(layout_dict, f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved layout: {filename}")
