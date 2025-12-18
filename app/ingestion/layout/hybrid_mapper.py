"""
Hybrid Mapping Algorithm for combining GCV text with Surya layout regions.

This module implements the core algorithm that maps Google Cloud Vision
word annotations to Surya layout regions based on bounding box overlap (IoU).

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

from typing import List, Optional, Tuple

from loguru import logger

from .models import GCVWord, LayoutRegion, MappedRegion, RegionLabel


class HybridMapper:
    """
    Maps GCV words to Surya layout regions based on IoU overlap.

    The mapping algorithm:
    1. For each word, calculate overlap with all regions
    2. Assign word to region with highest overlap if >= threshold
    3. If no region meets threshold, assign to default "Text" region
    4. Sort words within each region by reading order (Y, then X)

    Requirements:
        - 2.1: Assign words to regions with >60% overlap
        - 2.2: Handle tie-breaking with highest overlap
        - 2.3: Assign unmatched words to default "Text" region
        - 2.4: Sort words by reading order
    """

    DEFAULT_IOU_THRESHOLD = 0.6

    def __init__(self, iou_threshold: float = DEFAULT_IOU_THRESHOLD):
        """
        Initialize the HybridMapper.

        Args:
            iou_threshold: Minimum overlap percentage for word-to-region
                          assignment. Default is 0.6 (60%).
        """
        if not 0 < iou_threshold <= 1:
            raise ValueError(f"iou_threshold must be in (0, 1], got {iou_threshold}")
        self.iou_threshold = iou_threshold

    def map_words_to_regions(
        self,
        words: List[GCVWord],
        regions: List[LayoutRegion],
        page_width: int,
        page_height: int,
    ) -> List[MappedRegion]:
        """
        Map GCV words to layout regions based on IoU overlap.

        Args:
            words: List of GCVWord objects from GCV API.
            regions: List of LayoutRegion objects from Surya.
            page_width: Page width in pixels (for coordinate normalization).
            page_height: Page height in pixels (for coordinate normalization).

        Returns:
            List of MappedRegion objects, each containing a region and its
            assigned words sorted by reading order.

        Property 2: Word-to-Region Assignment
        For any GCV word and set of layout regions:
        - If word has >=60% overlap with exactly one region, assign to that region
        - If word overlaps multiple regions, assign to region with highest overlap
        - If no region has >=60% overlap, assign to default "Text" region
        """
        if not words:
            return [MappedRegion(region=r, words=[], text="") for r in regions]

        if page_width <= 0 or page_height <= 0:
            raise ValueError(f"Invalid page dimensions: {page_width}x{page_height}")

        # Initialize region-to-words mapping
        region_words: dict[int, List[GCVWord]] = {i: [] for i in range(len(regions))}
        unassigned_words: List[GCVWord] = []

        # Process each word
        for word in words:
            # Normalize word bbox to 0-1 range
            word_bbox_normalized = self._normalize_bbox(
                word.bbox, page_width, page_height
            )

            # Find best matching region
            best_region_idx: Optional[int] = None
            best_overlap: float = 0.0

            for idx, region in enumerate(regions):
                overlap = self._calculate_overlap(word_bbox_normalized, region.bbox)

                if overlap >= self.iou_threshold and overlap > best_overlap:
                    best_overlap = overlap
                    best_region_idx = idx

            # Assign word to best region or mark as unassigned
            if best_region_idx is not None:
                region_words[best_region_idx].append(word)
            else:
                unassigned_words.append(word)

        # Build MappedRegion objects
        mapped_regions: List[MappedRegion] = []

        for idx, region in enumerate(regions):
            words_in_region = region_words[idx]
            sorted_words = self._sort_by_reading_order(words_in_region)
            text = " ".join(w.text for w in sorted_words)

            mapped_regions.append(
                MappedRegion(region=region, words=sorted_words, text=text)
            )

        # Handle unassigned words - create default Text region
        if unassigned_words:
            sorted_unassigned = self._sort_by_reading_order(unassigned_words)

            # Calculate bounding box for unassigned words
            default_bbox = self._calculate_bounding_box(
                sorted_unassigned, page_width, page_height
            )

            default_region = LayoutRegion(
                bbox=default_bbox, label=RegionLabel.TEXT.value, confidence=0.0
            )

            text = " ".join(w.text for w in sorted_unassigned)
            mapped_regions.append(
                MappedRegion(region=default_region, words=sorted_unassigned, text=text)
            )

            logger.debug(
                f"Created default Text region for {len(unassigned_words)} unassigned words"
            )

        return mapped_regions

    def _calculate_overlap(
        self,
        word_bbox: Tuple[float, float, float, float],
        region_bbox: Tuple[float, float, float, float],
    ) -> float:
        """
        Calculate the overlap percentage of a word within a region.

        This calculates what percentage of the word's area falls within
        the region's bounding box.

        Args:
            word_bbox: Word bounding box (x0, y0, x1, y1) normalized 0-1.
            region_bbox: Region bounding box (x0, y0, x1, y1) normalized 0-1.

        Returns:
            Overlap percentage (0-1). Returns 0 if word has zero area.
        """
        w_x0, w_y0, w_x1, w_y1 = word_bbox
        r_x0, r_y0, r_x1, r_y1 = region_bbox

        # Calculate word area
        word_area = (w_x1 - w_x0) * (w_y1 - w_y0)
        if word_area <= 0:
            return 0.0

        # Calculate intersection
        inter_x0 = max(w_x0, r_x0)
        inter_y0 = max(w_y0, r_y0)
        inter_x1 = min(w_x1, r_x1)
        inter_y1 = min(w_y1, r_y1)

        # Check if there's an intersection
        if inter_x0 >= inter_x1 or inter_y0 >= inter_y1:
            return 0.0

        # Calculate intersection area
        inter_area = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)

        # Return overlap as percentage of word area
        return inter_area / word_area

    def _normalize_bbox(
        self, bbox: Tuple[float, float, float, float], page_width: int, page_height: int
    ) -> Tuple[float, float, float, float]:
        """
        Normalize pixel coordinates to 0-1 range.

        Args:
            bbox: Bounding box in pixels (x0, y0, x1, y1).
            page_width: Page width in pixels.
            page_height: Page height in pixels.

        Returns:
            Normalized bounding box (x0, y0, x1, y1) in 0-1 range.
        """
        x0, y0, x1, y1 = bbox
        return (x0 / page_width, y0 / page_height, x1 / page_width, y1 / page_height)

    def _sort_by_reading_order(self, words: List[GCVWord]) -> List[GCVWord]:
        """
        Sort words by reading order: Y-coordinate ascending, then X-coordinate.

        Args:
            words: List of GCVWord objects.

        Returns:
            Sorted list of GCVWord objects.

        Property 3: Reading Order Sorting
        For any list of words, the output SHALL be sorted by Y-coordinate
        ascending, then by X-coordinate ascending.
        """
        return sorted(words, key=lambda w: (w.bbox[1], w.bbox[0]))

    def _calculate_bounding_box(
        self, words: List[GCVWord], page_width: int, page_height: int
    ) -> Tuple[float, float, float, float]:
        """
        Calculate the bounding box that encompasses all words.

        Args:
            words: List of GCVWord objects.
            page_width: Page width in pixels.
            page_height: Page height in pixels.

        Returns:
            Normalized bounding box (x0, y0, x1, y1) in 0-1 range.
        """
        if not words:
            return (0.0, 0.0, 1.0, 1.0)

        min_x = min(w.bbox[0] for w in words)
        min_y = min(w.bbox[1] for w in words)
        max_x = max(w.bbox[2] for w in words)
        max_y = max(w.bbox[3] for w in words)

        return (
            min_x / page_width,
            min_y / page_height,
            max_x / page_width,
            max_y / page_height,
        )
