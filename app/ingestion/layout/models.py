"""
Data models for Hybrid Layout-Aware Extraction.

This module defines the core data structures used throughout the hybrid
layout extraction pipeline, including layout regions from Surya, words
from Google Cloud Vision, and mapped regions combining both.

Requirements: 1.2, 2.5
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class RegionLabel(str, Enum):
    """
    Valid labels for layout regions detected by Surya.

    Requirements: 1.2 - The Layout_Detection_Module SHALL classify the region
    as one of these types.
    """

    SECTION_HEADER = "Section_Header"
    TITLE = "Title"
    TABLE = "Table"
    TEXT = "Text"
    LIST = "List"
    CAPTION = "Caption"
    FOOTNOTE = "Footnote"
    PAGE_FOOTER = "Page_Footer"

    @classmethod
    def is_valid(cls, label: str) -> bool:
        """Check if a label string is a valid RegionLabel."""
        return label in [member.value for member in cls]

    @classmethod
    def get_all_values(cls) -> List[str]:
        """Return all valid label values."""
        return [member.value for member in cls]


@dataclass
class LayoutRegion:
    """
    Represents a detected layout region from Surya Layout model.

    Attributes:
        bbox: Bounding box coordinates (x0, y0, x1, y1) normalized to 0-1 range
        label: Region type classification
        confidence: Detection confidence score (0-1)

    Requirements: 1.1, 1.2
    """

    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1) normalized 0-1
    label: str  # One of RegionLabel values
    confidence: float = 0.0

    def __post_init__(self):
        """Validate bbox coordinates and label."""
        x0, y0, x1, y1 = self.bbox
        if not (0 <= x0 <= x1 <= 1 and 0 <= y0 <= y1 <= 1):
            # Allow slightly out-of-bounds values, clamp them
            self.bbox = (
                max(0, min(1, x0)),
                max(0, min(1, y0)),
                max(0, min(1, x1)),
                max(0, min(1, y1)),
            )

        if not RegionLabel.is_valid(self.label):
            # Default to TEXT for unknown labels
            self.label = RegionLabel.TEXT.value

    @property
    def width(self) -> float:
        """Calculate region width."""
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        """Calculate region height."""
        return self.bbox[3] - self.bbox[1]

    @property
    def area(self) -> float:
        """Calculate region area."""
        return self.width * self.height


@dataclass
class GCVWord:
    """
    Represents a word extracted from Google Cloud Vision API.

    Attributes:
        text: The recognized text content
        bbox: Bounding box coordinates (x0, y0, x1, y1) in pixels

    Requirements: 2.1
    """

    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1) in pixels

    @property
    def center_x(self) -> float:
        """Calculate horizontal center of word."""
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def center_y(self) -> float:
        """Calculate vertical center of word."""
        return (self.bbox[1] + self.bbox[3]) / 2

    @property
    def width(self) -> float:
        """Calculate word width."""
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        """Calculate word height."""
        return self.bbox[3] - self.bbox[1]

    @property
    def area(self) -> float:
        """Calculate word area."""
        return self.width * self.height


@dataclass
class MappedRegion:
    """
    Represents a layout region with associated GCV words.

    This is the result of the hybrid mapping algorithm that combines
    Surya layout detection with GCV text recognition.

    Attributes:
        region: The original LayoutRegion from Surya
        words: List of GCVWords assigned to this region, sorted by reading order
        text: Concatenated text from all words

    Requirements: 2.4, 2.5
    """

    region: LayoutRegion
    words: List[GCVWord] = field(default_factory=list)
    text: str = ""

    def __post_init__(self):
        """Build text from words if not provided."""
        if not self.text and self.words:
            self.text = " ".join(word.text for word in self.words)

    @property
    def label(self) -> str:
        """Convenience accessor for region label."""
        return self.region.label

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Convenience accessor for region bbox."""
        return self.region.bbox

    @property
    def word_count(self) -> int:
        """Return number of words in this region."""
        return len(self.words)


@dataclass
class TableCell:
    """
    Represents a cell in a reconstructed table.

    Attributes:
        row: Row index (0-based)
        col: Column index (0-based)
        text: Cell content

    Requirements: 3.1, 3.2
    """

    row: int
    col: int
    text: str

    def __post_init__(self):
        """Validate row and column indices."""
        if self.row < 0:
            raise ValueError(f"Row index must be non-negative, got {self.row}")
        if self.col < 0:
            raise ValueError(f"Column index must be non-negative, got {self.col}")


@dataclass
class HybridExtractionResult:
    """
    Result of hybrid layout extraction for a single page.

    Attributes:
        page_num: Page number (1-based)
        regions: List of mapped regions with text
        markdown: Assembled Markdown output
        heading_count: Number of heading regions detected
        table_count: Number of table regions detected
        fallback_used: Whether GCV fallback was used due to layout detection failure

    Requirements: 5.1, 5.3
    """

    page_num: int
    regions: List[MappedRegion] = field(default_factory=list)
    markdown: str = ""
    heading_count: int = 0
    table_count: int = 0
    fallback_used: bool = False

    def __post_init__(self):
        """Calculate heading and table counts from regions."""
        if self.regions and self.heading_count == 0 and self.table_count == 0:
            for region in self.regions:
                if region.label in (
                    RegionLabel.SECTION_HEADER.value,
                    RegionLabel.TITLE.value,
                ):
                    self.heading_count += 1
                elif region.label == RegionLabel.TABLE.value:
                    self.table_count += 1
