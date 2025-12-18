"""
Tests for TableReconstructor.

This module contains unit tests and property-based tests for the
TableReconstructor class that reconstructs Markdown tables from
GCV words mapped to Table regions.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.2
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.ingestion.layout.models import GCVWord
from app.ingestion.table_reconstructor import TableReconstructor

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def reconstructor():
    """Default TableReconstructor instance."""
    return TableReconstructor(row_tolerance=0.02, min_rows=2)


@pytest.fixture
def lenient_reconstructor():
    """TableReconstructor with higher row tolerance."""
    return TableReconstructor(row_tolerance=0.1, min_rows=2)


# =============================================================================
# Unit Tests: Initialization
# =============================================================================


class TestTableReconstructorInit:
    """Tests for TableReconstructor initialization."""

    def test_default_values(self):
        """Test default initialization values."""
        tr = TableReconstructor()
        assert tr.row_tolerance == 0.02
        assert tr.min_rows == 2

    def test_custom_values(self):
        """Test custom initialization values."""
        tr = TableReconstructor(row_tolerance=0.05, min_rows=3)
        assert tr.row_tolerance == 0.05
        assert tr.min_rows == 3

    def test_invalid_row_tolerance_zero(self):
        """Test that row_tolerance=0 raises ValueError."""
        with pytest.raises(ValueError, match="row_tolerance must be in"):
            TableReconstructor(row_tolerance=0)

    def test_invalid_row_tolerance_negative(self):
        """Test that negative row_tolerance raises ValueError."""
        with pytest.raises(ValueError, match="row_tolerance must be in"):
            TableReconstructor(row_tolerance=-0.1)

    def test_invalid_row_tolerance_too_large(self):
        """Test that row_tolerance > 1 raises ValueError."""
        with pytest.raises(ValueError, match="row_tolerance must be in"):
            TableReconstructor(row_tolerance=1.5)

    def test_invalid_min_rows(self):
        """Test that min_rows < 1 raises ValueError."""
        with pytest.raises(ValueError, match="min_rows must be"):
            TableReconstructor(min_rows=0)


# =============================================================================
# Unit Tests: Row Grouping
# =============================================================================


class TestRowGrouping:
    """Tests for _group_into_rows method."""

    def test_empty_words(self, reconstructor):
        """Test grouping with empty word list."""
        rows = reconstructor._group_into_rows([])
        assert rows == []

    def test_single_word(self, reconstructor):
        """Test grouping with single word."""
        word = GCVWord(text="hello", bbox=(10, 100, 50, 120))
        rows = reconstructor._group_into_rows([word])
        assert len(rows) == 1
        assert len(rows[0]) == 1
        assert rows[0][0].text == "hello"

    def test_words_same_row(self, lenient_reconstructor):
        """Test words on same Y-level grouped together."""
        words = [
            GCVWord(text="A", bbox=(100, 100, 120, 120)),
            GCVWord(text="B", bbox=(10, 100, 30, 120)),
            GCVWord(text="C", bbox=(50, 100, 70, 120)),
        ]
        rows = lenient_reconstructor._group_into_rows(words)
        assert len(rows) == 1
        # Should be sorted by X: B, C, A
        assert [w.text for w in rows[0]] == ["B", "C", "A"]

    def test_words_different_rows(self, lenient_reconstructor):
        """Test words on different Y-levels grouped into separate rows."""
        words = [
            GCVWord(text="Row1A", bbox=(10, 100, 50, 120)),
            GCVWord(text="Row1B", bbox=(60, 100, 100, 120)),
            GCVWord(text="Row2A", bbox=(10, 200, 50, 220)),
            GCVWord(text="Row2B", bbox=(60, 200, 100, 220)),
        ]
        rows = lenient_reconstructor._group_into_rows(words)
        assert len(rows) == 2
        assert [w.text for w in rows[0]] == ["Row1A", "Row1B"]
        assert [w.text for w in rows[1]] == ["Row2A", "Row2B"]

    def test_x_sorting_within_row(self, lenient_reconstructor):
        """Test that words within a row are sorted by X-coordinate."""
        words = [
            GCVWord(text="Third", bbox=(200, 100, 250, 120)),
            GCVWord(text="First", bbox=(10, 100, 50, 120)),
            GCVWord(text="Second", bbox=(100, 100, 150, 120)),
        ]
        rows = lenient_reconstructor._group_into_rows(words)
        assert len(rows) == 1
        assert [w.text for w in rows[0]] == ["First", "Second", "Third"]


# =============================================================================
# Unit Tests: Markdown Generation
# =============================================================================


class TestMarkdownGeneration:
    """Tests for _to_markdown method."""

    def test_empty_table(self, reconstructor):
        """Test Markdown generation with empty data."""
        result = reconstructor._to_markdown([])
        assert result == ""

    def test_simple_table(self, reconstructor):
        """Test simple 2x2 table."""
        data = [
            ["Header1", "Header2"],
            ["Cell1", "Cell2"],
        ]
        result = reconstructor._to_markdown(data)
        expected = "| Header1 | Header2 |\n| --- | --- |\n| Cell1 | Cell2 |"
        assert result == expected

    def test_table_with_uneven_rows(self, reconstructor):
        """Test table with rows of different lengths."""
        data = [
            ["A", "B", "C"],
            ["D", "E"],  # Missing one column
        ]
        result = reconstructor._to_markdown(data)
        lines = result.split("\n")
        assert len(lines) == 3
        # Second data row should be padded
        assert lines[2] == "| D | E |  |"

    def test_table_with_pipe_character(self, reconstructor):
        """Test that pipe characters in cells are escaped."""
        data = [
            ["A|B", "C"],
            ["D", "E|F"],
        ]
        result = reconstructor._to_markdown(data)
        assert "A\\|B" in result
        assert "E\\|F" in result


# =============================================================================
# Unit Tests: Reconstruct Method
# =============================================================================


class TestReconstruct:
    """Tests for reconstruct method."""

    def test_empty_words(self, reconstructor):
        """Test reconstruction with empty word list."""
        result = reconstructor.reconstruct([])
        assert result == ""

    def test_single_row_returns_plain_text(self, reconstructor):
        """Test that single row returns plain text (min_rows=2)."""
        words = [
            GCVWord(text="A", bbox=(10, 100, 30, 120)),
            GCVWord(text="B", bbox=(50, 100, 70, 120)),
        ]
        result = reconstructor.reconstruct(words)
        # Should be plain text, not markdown table
        assert "|" not in result
        assert "A" in result and "B" in result

    def test_two_rows_returns_markdown_table(self, lenient_reconstructor):
        """Test that two rows returns Markdown table."""
        words = [
            GCVWord(text="H1", bbox=(10, 100, 30, 120)),
            GCVWord(text="H2", bbox=(50, 100, 70, 120)),
            GCVWord(text="D1", bbox=(10, 200, 30, 220)),
            GCVWord(text="D2", bbox=(50, 200, 70, 220)),
        ]
        result = lenient_reconstructor.reconstruct(words)
        assert "|" in result
        assert "---" in result
        assert "H1" in result and "D2" in result

    def test_min_rows_3(self):
        """Test with min_rows=3."""
        tr = TableReconstructor(row_tolerance=0.1, min_rows=3)
        words = [
            GCVWord(text="R1", bbox=(10, 100, 30, 120)),
            GCVWord(text="R2", bbox=(10, 200, 30, 220)),
        ]
        result = tr.reconstruct(words)
        # Only 2 rows, should be plain text
        assert "|" not in result


# =============================================================================
# Unit Tests: Parse Markdown Table
# =============================================================================


class TestParseMarkdownTable:
    """Tests for parse_markdown_table static method."""

    def test_empty_string(self):
        """Test parsing empty string."""
        result = TableReconstructor.parse_markdown_table("")
        assert result == []

    def test_simple_table(self):
        """Test parsing simple table."""
        markdown = "| A | B |\n| --- | --- |\n| C | D |"
        result = TableReconstructor.parse_markdown_table(markdown)
        assert result == [["A", "B"], ["C", "D"]]

    def test_table_with_escaped_pipe(self):
        """Test parsing table with escaped pipe."""
        markdown = "| A\\|B | C |\n| --- | --- |\n| D | E |"
        result = TableReconstructor.parse_markdown_table(markdown)
        assert result[0][0] == "A|B"

    def test_whitespace_handling(self):
        """Test that whitespace is trimmed from cells."""
        markdown = "|  A  |  B  |\n| --- | --- |\n|  C  |  D  |"
        result = TableReconstructor.parse_markdown_table(markdown)
        assert result == [["A", "B"], ["C", "D"]]


# =============================================================================
# Property-Based Tests
# =============================================================================


# Strategies for generating test data
@st.composite
def gcv_word_strategy(draw, y_range=(0, 1000)):
    """Generate a random GCVWord."""
    x0 = draw(
        st.floats(min_value=0, max_value=900, allow_nan=False, allow_infinity=False)
    )
    y0 = draw(
        st.floats(
            min_value=y_range[0],
            max_value=y_range[1] - 10,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    width = draw(
        st.floats(min_value=10, max_value=100, allow_nan=False, allow_infinity=False)
    )
    height = draw(
        st.floats(min_value=10, max_value=50, allow_nan=False, allow_infinity=False)
    )
    text = draw(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters=" "
            ),
        )
    )
    assume(text.strip())  # Ensure non-empty text
    return GCVWord(text=text.strip(), bbox=(x0, y0, x0 + width, y0 + height))


@st.composite
def table_row_strategy(draw, y_center: float, num_cols: int):
    """Generate a row of GCVWords at a specific Y position."""
    words = []
    x_pos = 10
    for _ in range(num_cols):
        text = draw(
            st.text(
                min_size=1,
                max_size=10,
                alphabet=st.characters(whitelist_categories=("L", "N")),
            )
        )
        assume(text.strip())
        width = draw(
            st.floats(min_value=20, max_value=80, allow_nan=False, allow_infinity=False)
        )
        height = 20
        word = GCVWord(
            text=text.strip(),
            bbox=(x_pos, y_center - height / 2, x_pos + width, y_center + height / 2),
        )
        words.append(word)
        x_pos += width + draw(
            st.floats(min_value=5, max_value=30, allow_nan=False, allow_infinity=False)
        )
    return words


@st.composite
def table_data_strategy(draw, min_rows=2, max_rows=6, min_cols=2, max_cols=5):
    """Generate valid 2D table data."""
    num_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    num_cols = draw(st.integers(min_value=min_cols, max_value=max_cols))

    table = []
    for _ in range(num_rows):
        row = []
        for _ in range(num_cols):
            # Generate cell text without pipe characters for simpler testing
            cell = draw(
                st.text(
                    min_size=1,
                    max_size=10,
                    alphabet=st.characters(
                        whitelist_categories=("L", "N"), whitelist_characters=" "
                    ),
                )
            )
            assume(cell.strip())
            row.append(cell.strip())
        table.append(row)
    return table


class TestTableReconstructorProperties:
    """
    Property-based tests for TableReconstructor.

    **Feature: hybrid-layout-extraction, Property 4: Table Row Grouping**
    **Feature: hybrid-layout-extraction, Property 5: Table Round-Trip Consistency**
    """

    @given(table_data=table_data_strategy())
    @settings(max_examples=100)
    def test_row_grouping_y_proximity_property(self, table_data):
        """
        **Feature: hybrid-layout-extraction, Property 4: Table Row Grouping**

        *For any* set of words in a Table region, words with Y-coordinates
        within the row_tolerance threshold SHALL be grouped into the same row,
        and words within each row SHALL be sorted by X-coordinate ascending.

        **Validates: Requirements 3.1, 3.2**
        """
        # Create words with clear row separation
        words = []
        y_spacing = 100  # Large spacing between rows

        for row_idx, row in enumerate(table_data):
            y_center = 100 + row_idx * y_spacing
            x_pos = 10
            for cell_text in row:
                word = GCVWord(
                    text=cell_text,
                    bbox=(x_pos, y_center - 10, x_pos + 50, y_center + 10),
                )
                words.append(word)
                x_pos += 60

        reconstructor = TableReconstructor(row_tolerance=0.1, min_rows=1)
        rows = reconstructor._group_into_rows(words)

        # Property: Number of rows should match input
        assert len(rows) == len(table_data)

        # Property: Words within each row should be sorted by X
        for row in rows:
            x_coords = [w.center_x for w in row]
            assert x_coords == sorted(x_coords), "Words not sorted by X within row"

    @given(table_data=table_data_strategy())
    @settings(max_examples=100)
    def test_round_trip_consistency_property(self, table_data):
        """
        **Feature: hybrid-layout-extraction, Property 5: Table Round-Trip Consistency**

        *For any* valid table data (2D array of strings with ≥2 rows),
        converting to Markdown and parsing back SHALL produce an equivalent 2D array.

        **Validates: Requirements 3.5**
        """
        reconstructor = TableReconstructor()

        # Convert to Markdown
        markdown = reconstructor._to_markdown(table_data)

        # Parse back
        parsed = TableReconstructor.parse_markdown_table(markdown)

        # Property: Round-trip should preserve data
        assert len(parsed) == len(table_data), "Row count mismatch after round-trip"

        for orig_row, parsed_row in zip(table_data, parsed):
            assert len(parsed_row) >= len(orig_row), "Column count mismatch"
            for orig_cell, parsed_cell in zip(orig_row, parsed_row):
                assert (
                    orig_cell == parsed_cell
                ), f"Cell mismatch: {orig_cell} != {parsed_cell}"

    @given(
        num_rows=st.integers(min_value=2, max_value=5),
        num_cols=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=100)
    def test_x_sorting_within_rows_property(self, num_rows, num_cols):
        """
        **Feature: hybrid-layout-extraction, Property 4: Table Row Grouping**

        Verify X-coordinate sorting within rows.

        **Validates: Requirements 3.2**
        """
        import random

        # Create words with shuffled X positions
        words = []
        y_spacing = 100

        for row_idx in range(num_rows):
            y_center = 100 + row_idx * y_spacing
            x_positions = list(range(num_cols))
            random.shuffle(x_positions)

            for col_idx, x_order in enumerate(x_positions):
                x_pos = 10 + x_order * 60
                word = GCVWord(
                    text=f"R{row_idx}C{x_order}",
                    bbox=(x_pos, y_center - 10, x_pos + 50, y_center + 10),
                )
                words.append(word)

        reconstructor = TableReconstructor(row_tolerance=0.1, min_rows=1)
        rows = reconstructor._group_into_rows(words)

        # Property: Each row should have words sorted by X
        for row in rows:
            for i in range(len(row) - 1):
                assert (
                    row[i].center_x <= row[i + 1].center_x
                ), "Words not sorted by X coordinate"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for TableReconstructor."""

    def test_words_with_same_y_different_x(self, lenient_reconstructor):
        """Test words at exact same Y but different X."""
        words = [
            GCVWord(text="C", bbox=(200, 100, 220, 120)),
            GCVWord(text="A", bbox=(10, 100, 30, 120)),
            GCVWord(text="B", bbox=(100, 100, 120, 120)),
        ]
        rows = lenient_reconstructor._group_into_rows(words)
        assert len(rows) == 1
        assert [w.text for w in rows[0]] == ["A", "B", "C"]

    def test_many_rows(self, lenient_reconstructor):
        """Test with many rows."""
        words = []
        for i in range(10):
            words.append(GCVWord(text=f"Row{i}", bbox=(10, i * 100, 50, i * 100 + 20)))

        rows = lenient_reconstructor._group_into_rows(words)
        assert len(rows) == 10

    def test_single_column_table(self, lenient_reconstructor):
        """Test table with single column."""
        words = [
            GCVWord(text="A", bbox=(10, 100, 30, 120)),
            GCVWord(text="B", bbox=(10, 200, 30, 220)),
            GCVWord(text="C", bbox=(10, 300, 30, 320)),
        ]
        result = lenient_reconstructor.reconstruct(words)
        assert "|" in result
        assert "A" in result and "B" in result and "C" in result

    def test_empty_cell_handling(self, reconstructor):
        """Test that empty cells are handled in markdown."""
        data = [
            ["A", "B", "C"],
            ["D", "", "F"],
        ]
        result = reconstructor._to_markdown(data)
        assert "| D |  | F |" in result

    def test_special_characters_in_cells(self, reconstructor):
        """Test cells with special characters."""
        data = [
            ["Header", "Value"],
            ["Test*", "100%"],
        ]
        result = reconstructor._to_markdown(data)
        assert "Test*" in result
        assert "100%" in result
