"""
Table Extraction Module
Handles detection and extraction of tables from PDF pages using PyMuPDF
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from loguru import logger


@dataclass
class TableCell:
    """Represents a single cell in a table"""

    row: int
    col: int
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)

    def __str__(self) -> str:
        return f"Cell[{self.row},{self.col}]: {self.text}"


@dataclass
class TableData:
    """Represents extracted table data with structure"""

    page_num: int
    table_index: int  # Index of table on the page (0-based)
    bbox: Tuple[float, float, float, float]  # Table bounding box
    row_count: int
    col_count: int
    cells: List[List[str]]  # 2D array of cell text
    markdown: str  # Markdown representation
    confidence: float = 1.0  # Confidence score (0-1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "page_num": self.page_num,
            "table_index": self.table_index,
            "bbox": self.bbox,
            "row_count": self.row_count,
            "col_count": self.col_count,
            "cells": self.cells,
            "markdown": self.markdown,
            "confidence": self.confidence,
        }


class TableExtractor:
    """
    Extract tables from PDF pages using PyMuPDF's built-in table detection
    """

    def __init__(
        self,
        min_rows: int = 2,
        min_cols: int = 2,
        snap_tolerance: float = 3.0,
        join_tolerance: float = 3.0,
        edge_min_length: int = 3,
        min_words_vertical: int = 3,
        min_words_horizontal: int = 1,
    ):
        """
        Initialize table extractor with configuration

        Args:
            min_rows: Minimum number of rows to consider as table
            min_cols: Minimum number of columns to consider as table
            snap_tolerance: Tolerance for snapping table lines (pixels)
            join_tolerance: Tolerance for joining nearby table lines (pixels)
            edge_min_length: Minimum edge length for table detection (pixels)
            min_words_vertical: Minimum words for vertical text blocks
            min_words_horizontal: Minimum words for horizontal text blocks
        """
        self.min_rows = min_rows
        self.min_cols = min_cols
        self.snap_tolerance = snap_tolerance
        self.join_tolerance = join_tolerance
        self.edge_min_length = edge_min_length
        self.min_words_vertical = min_words_vertical
        self.min_words_horizontal = min_words_horizontal

        logger.info(
            f"TableExtractor initialized: "
            f"min_rows={min_rows}, min_cols={min_cols}, "
            f"snap_tolerance={snap_tolerance}"
        )

    def extract_tables_from_page(self, page, page_num: int) -> List[TableData]:
        """
        Extract all tables from a PDF page

        Args:
            page: PyMuPDF page object
            page_num: Page number (1-indexed)

        Returns:
            List of TableData objects
        """
        tables = []

        try:
            # Find tables using PyMuPDF's built-in table detection
            table_finder = page.find_tables(
                snap_tolerance=self.snap_tolerance,
                join_tolerance=self.join_tolerance,
                edge_min_length=self.edge_min_length,
                min_words_vertical=self.min_words_vertical,
                min_words_horizontal=self.min_words_horizontal,
            )

            if not table_finder.tables:
                logger.debug(f"No tables found on page {page_num}")
                return tables

            logger.info(f"Found {len(table_finder.tables)} table(s) on page {page_num}")

            # Process each detected table
            for table_index, table in enumerate(table_finder.tables):
                try:
                    table_data = self._extract_table_data(table, page_num, table_index)

                    # Validate table meets minimum requirements
                    if self._is_valid_table(table_data):
                        tables.append(table_data)
                        logger.debug(
                            f"Extracted table {table_index} from page {page_num}: "
                            f"{table_data.row_count}x{table_data.col_count}"
                        )
                    else:
                        logger.debug(
                            f"Table {table_index} on page {page_num} failed validation"
                        )

                except Exception as e:
                    logger.warning(
                        f"Failed to extract table {table_index} from page {page_num}: {e}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error finding tables on page {page_num}: {e}")

        return tables

    def _extract_table_data(self, table, page_num: int, table_index: int) -> TableData:
        """
        Extract structured data from a PyMuPDF table object

        Args:
            table: PyMuPDF Table object
            page_num: Page number
            table_index: Index of table on page

        Returns:
            TableData object with extracted content
        """
        # Get table dimensions
        row_count = table.row_count
        col_count = table.col_count
        bbox = table.bbox

        # Extract cells as 2D array
        cells = table.extract()

        # Clean cell text
        cleaned_cells = []
        for row in cells:
            cleaned_row = []
            for cell in row:
                # Clean cell text
                cell_text = self._clean_cell_text(cell)
                cleaned_row.append(cell_text)
            cleaned_cells.append(cleaned_row)

        # Convert to Markdown
        markdown = self._convert_to_markdown(cleaned_cells)

        # Create TableData object
        table_data = TableData(
            page_num=page_num,
            table_index=table_index,
            bbox=bbox,
            row_count=row_count,
            col_count=col_count,
            cells=cleaned_cells,
            markdown=markdown,
            confidence=self._calculate_confidence(cleaned_cells),
        )

        return table_data

    def _clean_cell_text(self, text: Any) -> str:
        """
        Clean text from a table cell

        Args:
            text: Cell text (can be str or None)

        Returns:
            Cleaned text string
        """
        if text is None:
            return ""

        if not isinstance(text, str):
            text = str(text)

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def _convert_to_markdown(self, cells: List[List[str]]) -> str:
        """
        Convert table cells to Markdown format

        Args:
            cells: 2D array of cell text

        Returns:
            Markdown formatted table string
        """
        if not cells or not cells[0]:
            return ""

        markdown_lines = []

        # Add header row (first row)
        header = cells[0]
        header_line = "| " + " | ".join(header) + " |"
        markdown_lines.append(header_line)

        # Add separator
        separator = "| " + " | ".join(["---"] * len(header)) + " |"
        markdown_lines.append(separator)

        # Add data rows
        for row in cells[1:]:
            # Ensure row has same number of columns as header
            while len(row) < len(header):
                row.append("")

            row_line = "| " + " | ".join(row[: len(header)]) + " |"
            markdown_lines.append(row_line)

        return "\n".join(markdown_lines)

    def _calculate_confidence(self, cells: List[List[str]]) -> float:
        """
        Calculate confidence score for table extraction

        Args:
            cells: 2D array of cell text

        Returns:
            Confidence score (0-1)
        """
        if not cells:
            return 0.0

        # Count non-empty cells
        total_cells = sum(len(row) for row in cells)
        non_empty_cells = sum(1 for row in cells for cell in row if cell.strip())

        if total_cells == 0:
            return 0.0

        # Base confidence on percentage of non-empty cells
        fill_ratio = non_empty_cells / total_cells

        # Boost confidence if structure looks good
        row_count = len(cells)
        col_counts = [len(row) for row in cells]

        # Check if all rows have same number of columns
        if len(set(col_counts)) == 1 and row_count >= self.min_rows:
            fill_ratio = min(1.0, fill_ratio * 1.2)

        return round(fill_ratio, 2)

    def _is_valid_table(self, table_data: TableData) -> bool:
        """
        Validate if extracted table meets minimum requirements

        Args:
            table_data: TableData object to validate

        Returns:
            True if valid, False otherwise
        """
        # Check minimum dimensions
        if table_data.row_count < self.min_rows:
            logger.debug(
                f"Table rejected: row_count={table_data.row_count} < {self.min_rows}"
            )
            return False

        if table_data.col_count < self.min_cols:
            logger.debug(
                f"Table rejected: col_count={table_data.col_count} < {self.min_cols}"
            )
            return False

        # Check if table has any content
        has_content = any(cell.strip() for row in table_data.cells for cell in row)

        if not has_content:
            logger.debug("Table rejected: no content")
            return False

        return True

    def extract_tables_from_document(self, pdf_path: str) -> Dict[int, List[TableData]]:
        """
        Extract tables from all pages in a PDF document

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary mapping page numbers to lists of TableData
        """
        all_tables = {}

        try:
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc[page_num]
                tables = self.extract_tables_from_page(page, page_num + 1)

                if tables:
                    all_tables[page_num + 1] = tables

            doc.close()

            total_tables = sum(len(tables) for tables in all_tables.values())
            logger.info(
                f"Extracted {total_tables} tables from {len(all_tables)} pages "
                f"in {pdf_path}"
            )

        except Exception as e:
            logger.error(f"Error extracting tables from {pdf_path}: {e}")
            raise

        return all_tables

    def format_table_for_chunk(self, table_data: TableData) -> str:
        """
        Format table for inclusion in text chunks

        Args:
            table_data: TableData object

        Returns:
            Formatted string with table metadata and content
        """
        lines = []

        # Add metadata header
        lines.append(f"\n<!-- TABLE {table_data.table_index + 1} -->")
        lines.append(
            f"<!-- Table: {table_data.row_count} rows × {table_data.col_count} cols -->"
        )

        # Add markdown table
        lines.append("")
        lines.append(table_data.markdown)
        lines.append("")

        # Add closing marker
        lines.append(f"<!-- END TABLE {table_data.table_index + 1} -->")

        return "\n".join(lines)


def extract_table_metadata_from_chunk(chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract table metadata from a chunk that may contain tables.

    Detects table markers like:
    - --- TABLE START (Page X, Table Y: RxC, confidence=Z) ---
    - Markdown tables (| col1 | col2 |)
    - <!-- TABLE X --> markers

    Args:
        chunk: Chunk dictionary with text, metadata, chunk_id, etc.

    Returns:
        List of table metadata dictionaries with schema:
        {
            "table_id": "<doc_id>_table_<page>_<idx>",
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "page": page_number,
            "table_index": table_index_on_page,
            "title": extracted_title_or_caption,
            "row_count": num_rows,
            "col_count": num_cols,
            "confidence": confidence_score,
            "cells": [[cell_values]],  # 2D array
            "markdown": markdown_representation,
            "has_torque_data": bool,  # Special flag for torque tables
            "keywords": ["M42", "anchor", "bolt"]  # Extracted keywords
        }
    """
    import re
    from typing import Any, Dict, List

    tables = []
    text = chunk.get("text", "")
    chunk_id = chunk.get("chunk_id", "unknown")
    doc_id = chunk.get("doc_id", "unknown")
    metadata = chunk.get("metadata", {})

    # Try to get page from metadata first, then from content
    page = metadata.get("page")
    if page is None:
        # Try to extract from text markers
        page_match = re.search(r"<!--\s*Page\s+(\d+)\s*-->", text, re.IGNORECASE)
        if page_match:
            page = int(page_match.group(1))
        else:
            page = chunk.get("page_start", 0)

    # Pattern 1: Detect TABLE START markers
    # --- TABLE START (Page 16, Table 1: 5x3, confidence=0.95) ---
    table_start_pattern = r"---\s*TABLE START\s*\(Page\s+(\d+),\s*Table\s+(\d+):\s*(\d+)x(\d+),\s*confidence=([\d.]+)\)\s*---"
    table_end_pattern = r"---\s*TABLE END\s*---"

    # Find all table blocks
    table_blocks = []
    start_matches = list(re.finditer(table_start_pattern, text, re.IGNORECASE))
    end_matches = list(re.finditer(table_end_pattern, text, re.IGNORECASE))

    for i, start_match in enumerate(start_matches):
        start_pos = start_match.end()

        # Find corresponding END marker
        end_pos = len(text)
        if i < len(end_matches):
            end_pos = end_matches[i].start()

        # Extract table markdown
        table_markdown = text[start_pos:end_pos].strip()

        # Parse metadata from START marker
        table_page = int(start_match.group(1))
        table_idx = int(start_match.group(2)) - 1  # 0-indexed
        row_count = int(start_match.group(3))
        col_count = int(start_match.group(4))
        confidence = float(start_match.group(5))

        # Extract cells from markdown
        cells = _parse_markdown_table(table_markdown)

        # Extract title/caption (look for text before table)
        title = _extract_table_title(text, start_match.start())

        # Detect special content (torque, anchor bolts, etc.)
        has_torque_data = _detect_torque_content(table_markdown)
        keywords = _extract_table_keywords(table_markdown)

        # Create table metadata
        table_id = f"{doc_id}_table_{table_page}_{table_idx}"
        table_meta = {
            "table_id": table_id,
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "page": table_page,
            "table_index": table_idx,
            "title": title,
            "row_count": row_count,
            "col_count": col_count,
            "confidence": confidence,
            "cells": cells,
            "markdown": table_markdown,
            "has_torque_data": has_torque_data,
            "keywords": keywords,
        }
        tables.append(table_meta)

    # Pattern 2: Detect raw markdown tables (no markers)
    # If no TABLE START markers found, look for plain markdown tables
    if not tables:
        markdown_tables = _detect_markdown_tables(text)
        for idx, (table_markdown, start_pos) in enumerate(markdown_tables):
            cells = _parse_markdown_table(table_markdown)
            if cells and len(cells) >= 2:  # At least header + 1 row
                row_count = len(cells)
                col_count = len(cells[0]) if cells else 0

                title = _extract_table_title(text, start_pos)
                has_torque_data = _detect_torque_content(table_markdown)
                keywords = _extract_table_keywords(table_markdown)

                table_id = f"{doc_id}_table_{page}_{idx}"
                table_meta = {
                    "table_id": table_id,
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "page": page,
                    "table_index": idx,
                    "title": title,
                    "row_count": row_count,
                    "col_count": col_count,
                    "confidence": 0.7,  # Lower confidence for unmarked tables
                    "cells": cells,
                    "markdown": table_markdown,
                    "has_torque_data": has_torque_data,
                    "keywords": keywords,
                }
                tables.append(table_meta)

    return tables


def _parse_markdown_table(markdown: str) -> List[List[str]]:
    """Parse markdown table into 2D cell array"""
    import re

    lines = markdown.strip().split("\n")
    cells = []

    for line in lines:
        # Skip separator lines (| --- | --- |)
        if re.match(r"^\|\s*[-:]+\s*(?:\|\s*[-:]+\s*)*\|?$", line.strip()):
            continue

        # Parse table row
        if "|" in line:
            # Remove leading/trailing pipes and split
            row = [cell.strip() for cell in line.strip(" |").split("|")]
            if row:  # Skip empty rows
                cells.append(row)

    return cells


def _extract_table_title(text: str, table_pos: int) -> str:
    """Extract table title/caption from text before table position"""
    import re

    # Look at text before table (up to 200 chars)
    prefix = text[max(0, table_pos - 200) : table_pos]

    # Look for common title patterns
    # "Table X: Title"
    match = re.search(r"Table\s+\d+[:\.]?\s*([^\n]+)", prefix, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Look for heading markers
    match = re.search(r"###?\s*([^\n]+)", prefix)
    if match:
        return match.group(1).strip()

    # Look for bold text **Title**
    match = re.search(r"\*\*([^*]+)\*\*", prefix)
    if match:
        return match.group(1).strip()

    return ""


def _detect_torque_content(text: str) -> bool:
    """Detect if table contains torque-related data"""
    import re

    torque_keywords = [
        r"\btorque\b",
        r"\bNm\b",
        r"\bkN[·.]?m\b",
        r"\bft[·-]?lbs?\b",
        r"\bM\d{2}\b",  # M42, M36, etc.
        r"\banchor\b",
        r"\bbolt\b",
    ]

    for pattern in torque_keywords:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def _extract_table_keywords(text: str) -> List[str]:
    """Extract important keywords from table content"""
    import re

    keywords = set()

    # Extract torque values (e.g., "1420 Nm", "500 kN.m")
    torque_matches = re.findall(
        r"\b\d+\.?\d*\s*(?:Nm|kN[·.]?m|ft[·-]?lbs?)\b", text, re.IGNORECASE
    )
    keywords.update(torque_matches)

    # Extract bolt sizes (e.g., "M42", "M36")
    bolt_matches = re.findall(r"\bM\d{2}\b", text)
    keywords.update(bolt_matches)

    # Extract common terms
    common_terms = ["anchor", "bolt", "torque", "installation", "tightening"]
    for term in common_terms:
        if re.search(rf"\b{term}\b", text, re.IGNORECASE):
            keywords.add(term.lower())

    return list(keywords)


def _detect_markdown_tables(text: str) -> List[tuple]:
    """Detect and extract plain markdown tables from text"""
    import re

    tables = []

    # Pattern: lines starting with |...|...|...
    # Markdown table: at least 2 consecutive lines with pipes
    lines = text.split("\n")

    table_start = None
    table_lines = []

    for i, line in enumerate(lines):
        # Check if line looks like table row
        if re.match(r"^\s*\|.*\|\s*$", line):
            if table_start is None:
                table_start = i
            table_lines.append(line)
        else:
            # End of table
            if table_start is not None and len(table_lines) >= 2:
                # Found a table
                table_markdown = "\n".join(table_lines)
                # Calculate position in original text
                start_pos = sum(len(lines[j]) + 1 for j in range(table_start))
                tables.append((table_markdown, start_pos))

            # Reset
            table_start = None
            table_lines = []

    # Check last table
    if table_start is not None and len(table_lines) >= 2:
        table_markdown = "\n".join(table_lines)
        start_pos = sum(len(lines[j]) + 1 for j in range(table_start))
        tables.append((table_markdown, start_pos))

    return tables


# Export main classes
__all__ = [
    "TableExtractor",
    "TableData",
    "TableCell",
    "extract_table_metadata_from_chunk",
]
