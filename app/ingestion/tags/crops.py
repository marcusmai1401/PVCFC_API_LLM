"""
Crop Generator
Render PNG crops of extracted tag bboxes for vision citations

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 6
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
from loguru import logger
from PIL import Image

from app.config import get_config

from .schemas import TagEntity


class CropGenerator:
    """Generate PNG crops from tag bboxes"""

    def __init__(self, dpi: int = 200):
        """
        Initialize crop generator

        Args:
            dpi: DPI for rendering (default 200, good balance of quality/size)
        """
        self.config = get_config()
        self.dpi = dpi

    def generate_crop(
        self,
        pdf_path: Path,
        tag: TagEntity,
        output_dir: Optional[Path] = None,
    ) -> Optional[str]:
        """
        Generate PNG crop for a single tag

        Args:
            pdf_path: Path to source PDF
            tag: TagEntity with bbox
            output_dir: Output directory (default: CROPS_DIR)

        Returns:
            Relative path to crop file, or None if failed
        """
        if output_dir is None:
            output_dir = self.config.CROPS_DIR

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            doc = fitz.open(str(pdf_path))
            page = doc[tag.page - 1]  # Convert to 0-based

            # Get bbox in page coordinates
            bbox = tag.bbox
            if len(bbox) != 4:
                logger.warning(f"Invalid bbox for tag {tag.tag}")
                return None

            # Create rect for cropping
            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])

            # Add small margin (5% of bbox dimensions)
            margin_x = (rect.x1 - rect.x0) * 0.05
            margin_y = (rect.y1 - rect.y0) * 0.05
            rect = rect + (-margin_x, -margin_y, margin_x, margin_y)

            # Clip to page boundaries
            rect = rect & page.rect

            # Render crop
            mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Generate filename
            # Format: {doc_id}_{page}_{tag_hash}.png
            tag_hash = hashlib.md5(tag.tag.encode()).hexdigest()[:8]
            filename = f"{tag.doc_id}_p{tag.page}_{tag_hash}.png"
            output_path = output_dir / filename

            # Save PNG
            pix.save(str(output_path))

            doc.close()

            # Return relative path from CROPS_DIR
            relative_path = filename

            logger.debug(f"Generated crop: {filename}")

            return relative_path

        except Exception as e:
            logger.error(f"Crop generation failed for tag {tag.tag}: {e}")
            return None

    def generate_crops_batch(
        self,
        pdf_path: Path,
        tags: List[TagEntity],
        output_dir: Optional[Path] = None,
    ) -> Dict[str, str]:
        """
        Generate crops for multiple tags from same PDF (more efficient)

        Args:
            pdf_path: Path to source PDF
            tags: List of TagEntity objects
            output_dir: Output directory

        Returns:
            Dict mapping tag.tag → crop_path
        """
        if output_dir is None:
            output_dir = self.config.CROPS_DIR

        crop_paths = {}

        # Group tags by page for efficiency
        tags_by_page = {}
        for tag in tags:
            if tag.page not in tags_by_page:
                tags_by_page[tag.page] = []
            tags_by_page[tag.page].append(tag)

        try:
            doc = fitz.open(str(pdf_path))

            for page_num, page_tags in tags_by_page.items():
                page = doc[page_num - 1]

                for tag in page_tags:
                    crop_path = self._generate_single_crop(page, tag, output_dir)
                    if crop_path:
                        crop_paths[tag.tag] = crop_path

            doc.close()

        except Exception as e:
            logger.error(f"Batch crop generation failed: {e}")

        logger.info(f"Generated {len(crop_paths)} crops for {pdf_path.name}")

        return crop_paths

    def _generate_single_crop(
        self,
        page: fitz.Page,
        tag: TagEntity,
        output_dir: Path,
    ) -> Optional[str]:
        """Generate crop for single tag (page already open)"""
        try:
            bbox = tag.bbox
            if len(bbox) != 4:
                return None

            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])

            # Add margin
            margin_x = (rect.x1 - rect.x0) * 0.05
            margin_y = (rect.y1 - rect.y0) * 0.05
            rect = rect + (-margin_x, -margin_y, margin_x, margin_y)
            rect = rect & page.rect

            # Render
            mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Filename
            tag_hash = hashlib.md5(tag.tag.encode()).hexdigest()[:8]
            filename = f"{tag.doc_id}_p{tag.page}_{tag_hash}.png"
            output_path = output_dir / filename

            pix.save(str(output_path))

            return filename

        except Exception as e:
            logger.debug(f"Single crop failed: {e}")
            return None
