"""
Markdown Builder for Hybrid Layout-Aware Extraction.

This module assembles layout regions into structured Markdown output,
applying appropriate formatting based on region type (headings, tables,
plain text) and excluding noise regions.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.4
"""

from typing import List, Optional, Set

from app.ingestion.layout.models import MappedRegion, RegionLabel
from app.ingestion.table_reconstructor import TableReconstructor


class MarkdownBuilder:
    """
    Assembles layout regions into structured Markdown.

    The builder applies formatting rules based on region type:
    - Section_Header/Title: Prefix with # or ##
    - Table: Insert reconstructed Markdown table
    - Text/List: Output as plain paragraphs
    - Caption/Footnote/Page_Footer: Exclude from output

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """

    # Region labels that should be formatted as headings
    HEADING_LABELS: Set[str] = {
        RegionLabel.SECTION_HEADER.value,
        RegionLabel.TITLE.value,
    }

    # Region labels that should be excluded from output
    EXCLUDED_LABELS: Set[str] = {
        RegionLabel.CAPTION.value,
        RegionLabel.FOOTNOTE.value,
        RegionLabel.PAGE_FOOTER.value,
    }

    # Region separator (double newline)
    REGION_SEPARATOR = "\n\n"

    def __init__(self, table_reconstructor: Optional[TableReconstructor] = None):
        """
        Initialize MarkdownBuilder.

        Args:
            table_reconstructor: TableReconstructor instance for table formatting.
                               If None, a default instance will be created.
        """
        self.table_reconstructor = table_reconstructor or TableReconstructor()

    def build(self, mapped_regions: List[MappedRegion], page_num: int) -> str:
        """
        Build Markdown from mapped regions.

        Args:
            mapped_regions: List of MappedRegion objects from HybridMapper
            page_num: Page number for page marker (1-based)

        Returns:
            Structured Markdown string with page marker

        Requirements: 4.5, 5.4

        Property 7: Region Separator
        For any two consecutive regions, they SHALL be separated by
        exactly double newline (\\n\\n).

        Property 8: Page Marker Preservation
        For any page, the output SHALL contain <!-- Page N --> marker.
        """
        if not mapped_regions:
            return f"<!-- Page {page_num} -->"

        # Format each region
        formatted_parts: List[str] = []

        for region in mapped_regions:
            formatted = self._format_region(region)
            if formatted:  # Skip None/empty results (excluded regions)
                formatted_parts.append(formatted)

        # Join with double newline separator
        content = self.REGION_SEPARATOR.join(formatted_parts)

        # Add page marker at the beginning
        page_marker = f"<!-- Page {page_num} -->"

        if content:
            return f"{page_marker}\n{content}"
        return page_marker

    def _format_region(self, region: MappedRegion) -> Optional[str]:
        """
        Format a single region to Markdown.

        Args:
            region: MappedRegion to format

        Returns:
            Formatted Markdown string, or None if region should be excluded

        Requirements: 4.1, 4.2, 4.3, 4.4

        Property 6: Region-to-Markdown Formatting
        - Section_Header/Title: output starts with # or ##
        - Table: output is valid Markdown table syntax
        - Text/List: output is plain text
        - Caption/Footnote/Page_Footer: output is None (excluded)
        """
        label = region.label
        text = region.text.strip() if region.text else ""

        # Exclude noise regions
        if label in self.EXCLUDED_LABELS:
            return None

        # Skip empty regions
        if not text and label != RegionLabel.TABLE.value:
            return None

        # Format based on region type
        if label in self.HEADING_LABELS:
            return self._format_heading(region)
        elif label == RegionLabel.TABLE.value:
            return self._format_table(region)
        else:
            # Text, List, or any other type - plain text
            return self._format_plain_text(region)

    def _format_heading(self, region: MappedRegion) -> Optional[str]:
        """
        Format heading region with Markdown heading syntax.

        Title regions get # (h1), Section_Header regions get ## (h2).

        Args:
            region: MappedRegion with heading label

        Returns:
            Markdown heading string

        Requirements: 4.1
        """
        text = region.text.strip()
        if not text:
            return None

        # Title gets h1, Section_Header gets h2
        if region.label == RegionLabel.TITLE.value:
            return f"# {text}"
        else:  # Section_Header
            return f"## {text}"

    def _format_table(self, region: MappedRegion) -> Optional[str]:
        """
        Format table region using TableReconstructor.

        Args:
            region: MappedRegion with Table label

        Returns:
            Markdown table string

        Requirements: 4.2
        """
        if not region.words:
            # No words in table region, return text if available
            return region.text.strip() if region.text else None

        # Use TableReconstructor to build Markdown table
        return self.table_reconstructor.reconstruct(
            words=region.words, region_bbox=region.bbox
        )

    def _format_plain_text(self, region: MappedRegion) -> Optional[str]:
        """
        Format text/list region as plain paragraph.

        Args:
            region: MappedRegion with Text or List label

        Returns:
            Plain text string

        Requirements: 4.3
        """
        text = region.text.strip()
        return text if text else None
