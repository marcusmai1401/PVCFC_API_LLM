"""
Layout Detection Module using Surya-OCR.

This module provides a singleton wrapper for the Surya Layout model,
enabling efficient layout detection across multiple PDF pages while
managing GPU resources.

Requirements: 1.1, 1.2, 1.3, 1.4, 6.1, 6.3
"""

import io
import threading
from typing import List, Optional

from loguru import logger
from PIL import Image

from .models import LayoutRegion, RegionLabel


class LayoutDetector:
    """
    Singleton wrapper for Surya Layout model.

    Uses thread-safe singleton pattern to ensure only one model instance
    is loaded in GPU memory across all pages and documents.

    Requirements:
        - 1.4: Use Singleton Pattern to load the Surya model once
        - 6.1: Prevent multiple model instances in VRAM
    """

    _instance: Optional["LayoutDetector"] = None
    _lock = threading.Lock()
    _initialized = False

    # Mapping from Surya labels to our RegionLabel values
    SURYA_LABEL_MAP = {
        "SectionHeader": RegionLabel.SECTION_HEADER.value,
        "Section-header": RegionLabel.SECTION_HEADER.value,
        "section_header": RegionLabel.SECTION_HEADER.value,
        "Title": RegionLabel.TITLE.value,
        "title": RegionLabel.TITLE.value,
        "Table": RegionLabel.TABLE.value,
        "table": RegionLabel.TABLE.value,
        "Text": RegionLabel.TEXT.value,
        "text": RegionLabel.TEXT.value,
        "Paragraph": RegionLabel.TEXT.value,
        "paragraph": RegionLabel.TEXT.value,
        "List-item": RegionLabel.LIST.value,
        "List": RegionLabel.LIST.value,
        "list": RegionLabel.LIST.value,
        "Caption": RegionLabel.CAPTION.value,
        "caption": RegionLabel.CAPTION.value,
        "Footnote": RegionLabel.FOOTNOTE.value,
        "footnote": RegionLabel.FOOTNOTE.value,
        "Footer": RegionLabel.PAGE_FOOTER.value,
        "Page-footer": RegionLabel.PAGE_FOOTER.value,
        "page_footer": RegionLabel.PAGE_FOOTER.value,
        "PageFooter": RegionLabel.PAGE_FOOTER.value,  # Surya 0.17.0 format
        "Header": RegionLabel.SECTION_HEADER.value,  # Map page header to section header
        "Page-header": RegionLabel.SECTION_HEADER.value,
        "PageHeader": RegionLabel.SECTION_HEADER.value,  # Surya 0.17.0 format
        "SectionHeader": RegionLabel.SECTION_HEADER.value,  # Surya 0.17.0 format
    }

    def __new__(cls) -> "LayoutDetector":
        """Ensure only one instance is created (singleton pattern)."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the detector (only runs once due to singleton)."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self._model = None
            self._processor = None
            self._device = None
            self._model_loaded = False
            self._initialized = True

            logger.info("LayoutDetector singleton instance created")

    @classmethod
    def get_instance(cls) -> "LayoutDetector":
        """
        Get the singleton instance of LayoutDetector.

        Returns:
            The singleton LayoutDetector instance.

        Property 1: Singleton Model Instance
        For any number of calls to get_instance(), the returned instance
        SHALL be the same object (identity equality).
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance (for testing purposes only).

        Warning: This should only be used in tests to ensure clean state.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.cleanup()
            cls._instance = None
            cls._initialized = False

    def _load_model(self) -> bool:
        """
        Load the Surya layout model.

        Returns:
            True if model loaded successfully, False otherwise.

        Requirements:
            - 1.3: Log error and return empty list on failure
            - 6.3: Handle CUDA out-of-memory error
        """
        if self._model_loaded:
            return True

        try:
            import torch

            # Determine device
            if torch.cuda.is_available():
                self._device = "cuda"
                logger.info("LayoutDetector: Using CUDA GPU for layout detection")
            else:
                self._device = "cpu"
                logger.info(
                    "LayoutDetector: Using CPU for layout detection (GPU not available)"
                )

            # Import surya modules - API changed in surya-ocr 0.17.0
            from surya.foundation import FoundationPredictor
            from surya.layout import LayoutPredictor

            # Load the layout model
            logger.info("Loading Surya layout model...")

            # Surya 0.17.0+ requires FoundationPredictor
            foundation = FoundationPredictor(device=self._device)
            self._model = LayoutPredictor(foundation)
            self._model_loaded = True
            logger.info("Surya layout model loaded successfully")

            return True

        except ImportError as e:
            logger.error(f"Failed to import Surya modules: {e}")
            return False
        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"CUDA out of memory while loading Surya model: {e}")
            return False
        except RuntimeError as e:
            logger.error(f"Runtime error loading Surya model: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error loading Surya model: {e}")
            return False

    def detect_layout(self, page_image: bytes) -> List[LayoutRegion]:
        """
        Detect layout regions from a page image.

        Args:
            page_image: Page image as bytes (PNG or JPEG format).

        Returns:
            List of LayoutRegion objects. Returns empty list on error
            to enable fallback processing.

        Requirements:
            - 1.1: Identify and return bounding boxes with labels
            - 1.2: Classify regions as valid RegionLabel types
            - 1.3: Return empty list on error for fallback

        Property 9: Valid Region Labels
        For any region returned, the label SHALL be one of the valid
        RegionLabel values.
        """
        try:
            # Load model if not already loaded
            if not self._load_model():
                logger.warning(
                    "Model not loaded, returning empty region list for fallback"
                )
                return []

            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(page_image))
            if image.mode != "RGB":
                image = image.convert("RGB")

            img_width, img_height = image.size

            # Run layout detection
            import torch

            with torch.no_grad():
                results = self._model([image])

            # Parse results
            regions = []
            if results and len(results) > 0:
                layout_result = results[0]

                # Surya returns LayoutResult with bboxes attribute
                for bbox_obj in layout_result.bboxes:
                    # Get bbox coordinates (already in pixel coordinates)
                    bbox = bbox_obj.bbox  # [x0, y0, x1, y1]

                    # Normalize to 0-1 range
                    x0 = bbox[0] / img_width
                    y0 = bbox[1] / img_height
                    x1 = bbox[2] / img_width
                    y1 = bbox[3] / img_height

                    # Get label and map to our RegionLabel
                    raw_label = bbox_obj.label
                    label = self._map_label(raw_label)

                    # Get confidence
                    confidence = getattr(bbox_obj, "confidence", 0.0)
                    if confidence is None:
                        confidence = getattr(bbox_obj, "score", 0.0) or 0.0

                    region = LayoutRegion(
                        bbox=(x0, y0, x1, y1), label=label, confidence=float(confidence)
                    )
                    regions.append(region)

            logger.debug(f"Detected {len(regions)} layout regions")
            return regions

        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"CUDA out of memory during layout detection: {e}")
            return []
        except RuntimeError as e:
            logger.error(f"Runtime error during layout detection: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during layout detection: {e}")
            return []

    def _map_label(self, raw_label: str) -> str:
        """
        Map Surya label to our RegionLabel value.

        Args:
            raw_label: Label string from Surya model.

        Returns:
            Mapped RegionLabel value, defaults to TEXT if unknown.
        """
        # Try direct mapping
        if raw_label in self.SURYA_LABEL_MAP:
            return self.SURYA_LABEL_MAP[raw_label]

        # Try case-insensitive matching
        raw_lower = raw_label.lower()
        for key, value in self.SURYA_LABEL_MAP.items():
            if key.lower() == raw_lower:
                return value

        # Default to TEXT for unknown labels
        logger.debug(f"Unknown Surya label '{raw_label}', mapping to TEXT")
        return RegionLabel.TEXT.value

    def cleanup(self) -> None:
        """
        Release GPU memory and cleanup resources.

        Requirements:
            - 6.2: Call torch.cuda.empty_cache() to release unused GPU memory
        """
        try:
            import torch

            self._model = None
            self._processor = None
            self._model_loaded = False

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("LayoutDetector: Released GPU memory")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    @property
    def is_model_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._model_loaded

    @property
    def device(self) -> Optional[str]:
        """Get the device being used (cuda or cpu)."""
        return self._device
