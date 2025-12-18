"""
Table Reconstructor for Hybrid Layout-Aware Extraction.

This module reconstructs Markdown tables from GCV words that have been
mapped to Table regions by the HybridMapper. It groups words into rows
based on Y-coordinate proximity and orders columns by X-coordinate.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import re
from typing import List, Optional, Tuple

from app.ingestion.layout.models import GCVWord, TableCell


class TableReconstructor:
    """
    Reconstructs Markdown tables from word coordinates.

    The reconstruction process:
    1. Group words into rows based on Y-coordinate proximity
    2. Sort words within each row by X-coordinate
    3. Convert to Markdown table format

    Requirements: 3.1, 3.2, 3.3, 3.4
    """

    def __init__(self, row_tolerance: float = 0.02, min_rows: int = 2):
        """
        Initialize TableReconstructor.

        Args:
            row_tolerance: Y-distance threshold for grouping words into same row.
                          Expressed as fraction of region height.
            min_rows: Minimum number of rows required to output as table.
                     Tables with fewer rows are returned as plain text.

        Raises:
            ValueError: If row_tolerance is not in (0, 1] or min_rows < 1
        """
        if not (0 < row_tolerance <= 1):
            raise ValueError(f"row_tolerance must be in (0, 1], got {row_tolerance}")
        if min_rows < 1:
            raise ValueError(f"min_rows must be >= 1, got {min_rows}")

        self.row_tolerance = row_tolerance
        self.min_rows = min_rows

    def reconstruct(
        self,
        words: List[GCVWord],
        region_bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> str:
        """
        Reconstruct Markdown table from words.

        Args:
            words: List of GCVWord objects within the table region
            region_bbox: Optional bounding box of the table region for
                        calculating relative positions

        Returns:
            Markdown table string if >= min_rows, otherwise plain text

        Requirements: 3.3, 3.4
        """
        if not words:
            return ""

        # Group words into rows
        rows = self._group_into_rows(words)

        # If fewer than min_rows, return as plain text
        if len(rows) < self.min_rows:
            return self._to_plain_text(rows)

        # Convert to 2D string array
        table_data = self._rows_to_2d_array(rows)

        # Generate Markdown table
        return self._to_markdown(table_data)

    def _group_into_rows(self, words: List[GCVWord]) -> List[List[GCVWord]]:
        """
        Group words into rows based on Y-coordinate proximity.

        Words are considered in the same row if their Y-centers are within
        row_tolerance of each other (relative to the overall Y-range).

        Args:
            words: List of GCVWord objects

        Returns:
            List of rows, where each row is a list of GCVWords sorted by X

        Requirements: 3.1
        """
        if not words:
            return []

        # Sort words by Y-center first
        sorted_words = sorted(words, key=lambda w: w.center_y)

        # Calculate Y-range for tolerance calculation
        min_y = min(w.bbox[1] for w in words)
        max_y = max(w.bbox[3] for w in words)
        y_range = max_y - min_y if max_y > min_y else 1.0

        # Absolute tolerance in pixels
        tolerance = y_range * self.row_tolerance

        rows: List[List[GCVWord]] = []
        current_row: List[GCVWord] = []
        current_row_y: Optional[float] = None

        for word in sorted_words:
            word_y = word.center_y

            if current_row_y is None:
                # First word starts a new row
                current_row = [word]
                current_row_y = word_y
            elif abs(word_y - current_row_y) <= tolerance:
                # Word is in the same row
                current_row.append(word)
            else:
                # Word starts a new row
                # Sort current row by X before adding
                current_row.sort(key=lambda w: w.center_x)
                rows.append(current_row)
                current_row = [word]
                current_row_y = word_y

        # Don't forget the last row
        if current_row:
            current_row.sort(key=lambda w: w.center_x)
            rows.append(current_row)

        return rows

    def _rows_to_2d_array(self, rows: List[List[GCVWord]]) -> List[List[str]]:
        """
        Convert rows of GCVWords to 2D string array.

        Args:
            rows: List of rows, each containing GCVWords

        Returns:
            2D array of cell text values

        Requirements: 3.2
        """
        return [[word.text for word in row] for row in rows]

    def _to_markdown(self, table_data: List[List[str]]) -> str:
        """
        Convert 2D array to Markdown table.

        Args:
            table_data: 2D array of cell values

        Returns:
            Valid Markdown table string with header separator row

        Requirements: 3.3
        """
        if not table_data:
            return ""

        # Normalize column count (pad shorter rows)
        max_cols = max(len(row) for row in table_data)
        normalized = [row + [""] * (max_cols - len(row)) for row in table_data]

        # Escape pipe characters in cell content
        escaped = [[cell.replace("|", "\\|") for cell in row] for row in normalized]

        lines = []

        # Header row (first row)
        header = "| " + " | ".join(escaped[0]) + " |"
        lines.append(header)

        # Separator row
        separator = "| " + " | ".join(["---"] * max_cols) + " |"
        lines.append(separator)

        # Data rows
        for row in escaped[1:]:
            data_line = "| " + " | ".join(row) + " |"
            lines.append(data_line)

        return "\n".join(lines)

    def _to_plain_text(self, rows: List[List[GCVWord]]) -> str:
        """
        Convert rows to plain text (for tables with fewer than min_rows).

        Args:
            rows: List of rows, each containing GCVWords

        Returns:
            Plain text with words joined by spaces

        Requirements: 3.4
        """
        text_parts = []
        for row in rows:
            row_text = " ".join(word.text for word in row)
            text_parts.append(row_text)
        return " ".join(text_parts)

    @staticmethod
    def parse_markdown_table(markdown: str) -> List[List[str]]:
        """
        Parse a Markdown table back to 2D array.

        This is used for round-trip consistency testing.

        Args:
            markdown: Markdown table string

        Returns:
            2D array of cell values

        Requirements: 3.5 (for testing round-trip consistency)
        """
        if not markdown or not markdown.strip():
            return []

        lines = markdown.strip().split("\n")
        if len(lines) < 2:
            return []

        result = []
        for i, line in enumerate(lines):
            # Skip separator row (contains only |, -, and spaces)
            if re.match(r"^\|[\s\-:|]+\|$", line):
                continue

            # Parse cells from line - handle escaped pipes
            line = line.strip()
            if line.startswith("|"):
                line = line[1:]
            if line.endswith("|"):
                line = line[:-1]

            # Split by unescaped pipes (not preceded by backslash)
            # Use regex to split properly
            cells = re.split(r"(?<!\\)\|", line)
            cells = [cell.strip().replace("\\|", "|") for cell in cells]
            result.append(cells)

        return result
