"""
Geometric Assembly Module for P&ID Tag Extraction

This module implements algorithms to assemble text fragments into complete tags
based on their spatial relationships (bounding boxes).

Key features:
- Parse Google Cloud Vision structured output
- Group vertically stacked text (e.g., "29", "TE", "2003B" → "29 TE 2003B")
- Validate assembled tags against P&ID patterns
- Extract bounding boxes for tag localization
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from loguru import logger


@dataclass(frozen=True)
class TextFragment:
    """Represents a single text fragment with its bounding box"""

    text: str
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float

    @property
    def center_x(self) -> float:
        """Get center X coordinate"""
        return self.bbox[0] + self.bbox[2] / 2

    @property
    def center_y(self) -> float:
        """Get center Y coordinate"""
        return self.bbox[1] + self.bbox[3] / 2

    @property
    def top(self) -> int:
        """Get top Y coordinate"""
        return self.bbox[1]

    @property
    def bottom(self) -> int:
        """Get bottom Y coordinate"""
        return self.bbox[1] + self.bbox[3]

    @property
    def left(self) -> int:
        """Get left X coordinate"""
        return self.bbox[0]

    @property
    def right(self) -> int:
        """Get right X coordinate"""
        return self.bbox[0] + self.bbox[2]


@dataclass
class AssembledTag:
    """Represents an assembled P&ID tag with metadata"""

    tag: str
    bbox: Tuple[int, int, int, int]  # Combined bbox of all fragments
    confidence: float
    fragments: List[TextFragment]
    pattern_match: str  # e.g., "vertical_3part", "horizontal_2part"


class GeometricAssembler:
    """
    Main class for geometric assembly of P&ID tags
    """

    def __init__(
        self,
        vertical_tolerance: float = 0.3,
        horizontal_tolerance: float = 0.2,
        min_confidence: float = 0.7,
    ):
        """
        Initialize geometric assembler

        Args:
            vertical_tolerance: Max horizontal deviation for vertical alignment (ratio of width)
            horizontal_tolerance: Max vertical deviation for horizontal alignment (ratio of height)
            min_confidence: Minimum OCR confidence threshold
        """
        self.vertical_tolerance = vertical_tolerance
        self.horizontal_tolerance = horizontal_tolerance
        self.min_confidence = min_confidence

        # P&ID tag patterns
        self.patterns = {
            "vertical_3part": re.compile(r"^(\d{2})\s+([A-Z]{2,3})\s+(\d{4}[AB]?)$"),
            "horizontal_3part": re.compile(
                r"^(\d{2})[-\s]?([A-Z]{2,3})[-\s]?(\d{4}[AB]?)$"
            ),
            "horizontal_merged": re.compile(
                r"^(\d{2})([A-Z]{2,3})(\d{4}[AB]?)$"
            ),  # No spaces, e.g., "29TE2003B"
        }

    def parse_vision_response(self, response) -> List[TextFragment]:
        """
        Parse Google Cloud Vision response to extract text fragments

        Args:
            response: Google Cloud Vision text detection response

        Returns:
            List of TextFragment objects
        """
        fragments = []

        # Skip first annotation (full text), process individual words
        for annotation in response.text_annotations[1:]:
            text = annotation.description.strip()

            # Get bounding box
            vertices = annotation.bounding_poly.vertices
            if len(vertices) >= 4:
                # Calculate bbox from vertices
                xs = [v.x for v in vertices]
                ys = [v.y for v in vertices]
                x = min(xs)
                y = min(ys)
                width = max(xs) - x
                height = max(ys) - y

                # Confidence (use 1.0 if not available, Vision API usually doesn't provide per-word confidence)
                confidence = getattr(annotation, "confidence", 1.0)

                fragment = TextFragment(
                    text=text, bbox=(x, y, width, height), confidence=confidence
                )
                fragments.append(fragment)

        logger.debug(f"Parsed {len(fragments)} text fragments from Vision API response")
        return fragments

    def find_vertical_neighbors(
        self,
        fragment: TextFragment,
        all_fragments: List[TextFragment],
        max_distance: int = 200,
    ) -> List[TextFragment]:
        """
        Find text fragments that are vertically aligned with the given fragment

        Args:
            fragment: Reference fragment
            all_fragments: All available fragments
            max_distance: Maximum vertical distance to consider

        Returns:
            List of vertically aligned fragments (sorted by Y position)
        """
        neighbors = []

        for other in all_fragments:
            if other is fragment:
                continue

            # Check vertical distance
            vertical_dist = abs(other.center_y - fragment.center_y)
            if vertical_dist > max_distance:
                continue

            # Check horizontal alignment (should have similar X center)
            horizontal_deviation = abs(other.center_x - fragment.center_x)
            max_horizontal_deviation = fragment.bbox[2] * self.vertical_tolerance

            if horizontal_deviation <= max_horizontal_deviation:
                neighbors.append(other)

        # Sort by Y position (top to bottom)
        neighbors.sort(key=lambda f: f.center_y)
        return neighbors

    def assemble_vertical_tag(
        self, fragments: List[TextFragment]
    ) -> Optional[AssembledTag]:
        """
        Attempt to assemble a vertical tag from 3 or 4 fragments

        Handles both:
        - 3-part: ["29", "TE", "2003B"]
        - 4-part: ["29", "TE", "2003", "B"] (split number code)

        Args:
            fragments: List of 3 or 4 text fragments (should be sorted top to bottom)

        Returns:
            AssembledTag if valid, None otherwise
        """
        if len(fragments) == 3:
            # Standard 3-part assembly
            return self._assemble_3part(fragments)
        elif len(fragments) == 4:
            # 4-part assembly (split number code)
            return self._assemble_4part(fragments)
        else:
            return None

    def _assemble_3part(self, fragments: List[TextFragment]) -> Optional[AssembledTag]:
        """
        Assemble 3-part vertical tag: [number, letters, code]
        Example: ["29", "TE", "2003B"]
        """
        if len(fragments) != 3:
            return None

        # Extract text components
        part1, part2, part3 = [f.text for f in fragments]

        # Check pattern: number(2) + letters(2-3) + code(4-5)
        if not (
            re.match(r"^\d{2}$", part1)
            and re.match(r"^[A-Z]{2,3}$", part2.upper())
            and re.match(r"^\d{4}[AB]?$", part3)
        ):
            return None

        # Assemble tag
        tag = f"{part1} {part2.upper()} {part3}"

        # Validate against pattern
        if not self.patterns["vertical_3part"].match(tag):
            return None

        # Calculate combined bounding box
        xs = [f.left for f in fragments] + [f.right for f in fragments]
        ys = [f.top for f in fragments] + [f.bottom for f in fragments]
        combined_bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

        # Calculate average confidence
        avg_confidence = sum(f.confidence for f in fragments) / len(fragments)

        return AssembledTag(
            tag=tag,
            bbox=combined_bbox,
            confidence=avg_confidence,
            fragments=fragments,
            pattern_match="vertical_3part",
        )

    def _assemble_4part(self, fragments: List[TextFragment]) -> Optional[AssembledTag]:
        """
        Assemble 4-part vertical tag: [number, letters, digits, letter]
        Example: ["29", "TE", "2003", "B"] → "29 TE 2003B"

        This handles cases where Vision API splits the number code like "2003B" into "2003" + "B"
        """
        if len(fragments) != 4:
            return None

        # Extract text components
        part1, part2, part3, part4 = [f.text for f in fragments]

        # Check pattern: number(2) + letters(2-3) + digits(4) + letter(1)
        if not (
            re.match(r"^\d{2}$", part1)
            and re.match(r"^[A-Z]{2,3}$", part2.upper())
            and re.match(r"^\d{4}$", part3)
            and re.match(r"^[AB]$", part4.upper())
        ):
            return None

        # Merge part3 + part4 to form complete number code
        number_code = f"{part3}{part4.upper()}"

        # Assemble tag
        tag = f"{part1} {part2.upper()} {number_code}"

        # Validate against pattern
        if not self.patterns["vertical_3part"].match(tag):
            return None

        # Calculate combined bounding box
        xs = [f.left for f in fragments] + [f.right for f in fragments]
        ys = [f.top for f in fragments] + [f.bottom for f in fragments]
        combined_bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

        # Calculate average confidence
        avg_confidence = sum(f.confidence for f in fragments) / len(fragments)

        return AssembledTag(
            tag=tag,
            bbox=combined_bbox,
            confidence=avg_confidence,
            fragments=fragments,
            pattern_match="vertical_4part_merged",
        )

    def _try_horizontal_tag(self, fragment: TextFragment) -> Optional[AssembledTag]:
        """
        Try to parse a single fragment as a complete horizontal tag
        Handles cases like "29TE2003B" merged into one fragment
        """
        text = fragment.text

        # Try pattern: 29TE2003B (no spaces)
        match = self.patterns["horizontal_merged"].match(text)
        if match:
            num, letters, code = match.groups()
            tag = f"{num} {letters.upper()} {code}"

            return AssembledTag(
                tag=tag,
                bbox=fragment.bbox,
                confidence=fragment.confidence,
                fragments=[fragment],
                pattern_match="horizontal_merged",
            )

        # Try pattern: 29 TE 2003B or 29-TE-2003B (with separators)
        match = self.patterns["horizontal_3part"].match(text)
        if match:
            num, letters, code = match.groups()
            tag = f"{num} {letters.upper()} {code}"

            return AssembledTag(
                tag=tag,
                bbox=fragment.bbox,
                confidence=fragment.confidence,
                fragments=[fragment],
                pattern_match="horizontal_3part",
            )

        return None

    def find_horizontal_neighbors(
        self,
        fragment: TextFragment,
        all_fragments: List[TextFragment],
        max_distance: int = 150,
    ) -> List[TextFragment]:
        """
        Find text fragments that are horizontally aligned (on same line)

        Args:
            fragment: Reference fragment
            all_fragments: All available fragments
            max_distance: Maximum horizontal distance to consider

        Returns:
            List of horizontally aligned fragments (sorted by X position)
        """
        neighbors = []

        for other in all_fragments:
            if other is fragment:
                continue

            # Check horizontal distance
            horizontal_dist = abs(other.center_x - fragment.center_x)
            if horizontal_dist > max_distance:
                continue

            # Check vertical alignment (should be on similar Y level)
            vertical_deviation = abs(other.center_y - fragment.center_y)
            max_vertical_deviation = fragment.bbox[3] * self.horizontal_tolerance

            if vertical_deviation <= max_vertical_deviation:
                neighbors.append(other)

        # Sort by X position (left to right)
        neighbors.sort(key=lambda f: f.center_x)
        return neighbors

    def assemble_horizontal_tag(
        self, fragments: List[TextFragment]
    ) -> Optional[AssembledTag]:
        """
        Attempt to assemble a horizontal tag from 3 or 4 fragments
        Example: ["29", "TE", "2003B"] or ["29", "TE", "2003", "B"]
        """
        if len(fragments) == 3:
            return self._assemble_horizontal_3part(fragments)
        elif len(fragments) == 4:
            return self._assemble_horizontal_4part(fragments)
        else:
            return None

    def _assemble_horizontal_3part(
        self, fragments: List[TextFragment]
    ) -> Optional[AssembledTag]:
        """
        Assemble 3-part horizontal tag: ["29", "TE", "2003B"]
        """
        if len(fragments) != 3:
            return None

        part1, part2, part3 = [f.text for f in fragments]

        # Check pattern
        if not (
            re.match(r"^\d{2}$", part1)
            and re.match(r"^[A-Z]{2,3}$", part2.upper())
            and re.match(r"^\d{4}[AB]?$", part3)
        ):
            return None

        tag = f"{part1} {part2.upper()} {part3}"

        # Validate
        if not self.patterns["vertical_3part"].match(tag):
            return None

        # Combined bbox
        xs = [f.left for f in fragments] + [f.right for f in fragments]
        ys = [f.top for f in fragments] + [f.bottom for f in fragments]
        combined_bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

        avg_confidence = sum(f.confidence for f in fragments) / len(fragments)

        return AssembledTag(
            tag=tag,
            bbox=combined_bbox,
            confidence=avg_confidence,
            fragments=fragments,
            pattern_match="horizontal_3part_assembled",
        )

    def _assemble_horizontal_4part(
        self, fragments: List[TextFragment]
    ) -> Optional[AssembledTag]:
        """
        Assemble 4-part horizontal tag: ["29", "TE", "2003", "B"]
        """
        if len(fragments) != 4:
            return None

        part1, part2, part3, part4 = [f.text for f in fragments]

        # Check pattern
        if not (
            re.match(r"^\d{2}$", part1)
            and re.match(r"^[A-Z]{2,3}$", part2.upper())
            and re.match(r"^\d{4}$", part3)
            and re.match(r"^[AB]$", part4.upper())
        ):
            return None

        number_code = f"{part3}{part4.upper()}"
        tag = f"{part1} {part2.upper()} {number_code}"

        # Validate
        if not self.patterns["vertical_3part"].match(tag):
            return None

        # Combined bbox
        xs = [f.left for f in fragments] + [f.right for f in fragments]
        ys = [f.top for f in fragments] + [f.bottom for f in fragments]
        combined_bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

        avg_confidence = sum(f.confidence for f in fragments) / len(fragments)

        return AssembledTag(
            tag=tag,
            bbox=combined_bbox,
            confidence=avg_confidence,
            fragments=fragments,
            pattern_match="horizontal_4part_merged",
        )

    def assemble_tags(self, fragments: List[TextFragment]) -> List[AssembledTag]:
        """
        Main method to assemble all tags from text fragments

        Args:
            fragments: List of text fragments from Vision API

        Returns:
            List of assembled tags
        """
        assembled_tags = []
        used_fragments = set()

        # Sort fragments by position (top to bottom, left to right)
        sorted_fragments = sorted(fragments, key=lambda f: (f.top, f.left))

        for fragment in sorted_fragments:
            if fragment in used_fragments:
                continue

            # Check if this could be the start of a tag (2-digit number)
            if not re.match(r"^\d{2}$", fragment.text):
                # Also try as complete horizontal tag
                horizontal_tag = self._try_horizontal_tag(fragment)
                if horizontal_tag:
                    assembled_tags.append(horizontal_tag)
                    used_fragments.add(fragment)
                    logger.debug(f"Assembled horizontal tag: {horizontal_tag.tag}")
                continue

            # Find vertical neighbors
            neighbors = self.find_vertical_neighbors(fragment, fragments)

            # Try 4-part assembly first (more specific)
            if len(neighbors) >= 3:
                candidate_fragments = [fragment] + neighbors[:3]
                tag = self.assemble_vertical_tag(candidate_fragments)
                if tag:
                    assembled_tags.append(tag)
                    used_fragments.update(candidate_fragments)
                    logger.debug(f"Assembled 4-part tag: {tag.tag} at bbox {tag.bbox}")
                    continue

            # Try 3-part assembly
            if len(neighbors) >= 2:
                candidate_fragments = [fragment] + neighbors[:2]
                tag = self.assemble_vertical_tag(candidate_fragments)
                if tag:
                    assembled_tags.append(tag)
                    used_fragments.update(candidate_fragments)
                    logger.debug(f"Assembled 3-part tag: {tag.tag} at bbox {tag.bbox}")
                    continue

            # Try horizontal neighbors
            h_neighbors = self.find_horizontal_neighbors(
                fragment, fragments, max_distance=150
            )

            # Try 4-part horizontal
            if len(h_neighbors) >= 3:
                candidate_fragments = [fragment] + h_neighbors[:3]
                tag = self.assemble_horizontal_tag(candidate_fragments)
                if tag:
                    assembled_tags.append(tag)
                    used_fragments.update(candidate_fragments)
                    logger.debug(f"Assembled horizontal 4-part tag: {tag.tag}")
                    continue

            # Try 3-part horizontal
            if len(h_neighbors) >= 2:
                candidate_fragments = [fragment] + h_neighbors[:2]
                tag = self.assemble_horizontal_tag(candidate_fragments)
                if tag:
                    assembled_tags.append(tag)
                    used_fragments.update(candidate_fragments)
                    logger.debug(f"Assembled horizontal 3-part tag: {tag.tag}")

        logger.info(
            f"Assembled {len(assembled_tags)} tags from {len(fragments)} fragments"
        )
        return assembled_tags

    def extract_tags_from_vision_response(self, response) -> List[AssembledTag]:
        """
        High-level method: Extract tags directly from Vision API response

        Args:
            response: Google Cloud Vision text detection response

        Returns:
            List of assembled tags
        """
        fragments = self.parse_vision_response(response)
        tags = self.assemble_tags(fragments)
        return tags


def extract_pid_tags_from_page(vision_response) -> List[dict]:
    """
    Convenience function to extract P&ID tags from a page

    Args:
        vision_response: Google Cloud Vision API response

    Returns:
        List of tag dictionaries with tag, bbox, confidence
    """
    assembler = GeometricAssembler()
    tags = assembler.extract_tags_from_vision_response(vision_response)

    return [
        {
            "tag": tag.tag,
            "bbox": tag.bbox,
            "confidence": tag.confidence,
            "pattern": tag.pattern_match,
        }
        for tag in tags
    ]
