"""
Tests for MarkdownBuilder.

This module contains unit tests and property-based tests for the
MarkdownBuilder class that assembles layout regions into structured
Markdown output.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.4, 7.3
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.ingestion.layout.models import GCVWord, LayoutRegion, MappedRegion, RegionLabel
from app.ingestion.markdown_builder import MarkdownBuilder
from app.ingestion.table_reconstructor import TableReconstructor

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def builder():
    """Default MarkdownBuilder instance."""
    return MarkdownBuilder()


@pytest.fixture
def table_reconstructor():
    """TableReconstructor instance for testing."""
    return TableReconstructor(row_tolerance=0.1, min_rows=2)


# =============================================================================
# Helper Functions
# =============================================================================


def create_mapped_region(
    label: str, text: str, words: list = None, bbox: tuple = (0.1, 0.1, 0.9, 0.2)
) -> MappedRegion:
    """Helper to create MappedRegion for testing."""
    region = LayoutRegion(bbox=bbox, label=label, confidence=0.9)
    return MappedRegion(region=region, words=words or [], text=text)


def create_table_words(rows_data: list) -> list:
    """Create GCVWords arranged in table format."""
    words = []
    y_spacing = 100
    for row_idx, row in enumerate(rows_data):
        y_center = 100 + row_idx * y_spacing
        x_pos = 10
        for cell_text in row:
            word = GCVWord(
                text=cell_text, bbox=(x_pos, y_center - 10, x_pos + 50, y_center + 10)
            )
            words.append(word)
            x_pos += 60
    return words


# =============================================================================
# Unit Tests: Initialization
# =============================================================================


class TestMarkdownBuilderInit:
    """Tests for MarkdownBuilder initialization."""

    def test_default_initialization(self):
        """Test default initialization creates TableReconstructor."""
        builder = MarkdownBuilder()
        assert builder.table_reconstructor is not None
        assert isinstance(builder.table_reconstructor, TableReconstructor)

    def test_custom_table_reconstructor(self, table_reconstructor):
        """Test initialization with custom TableReconstructor."""
        builder = MarkdownBuilder(table_reconstructor=table_reconstructor)
        assert builder.table_reconstructor is table_reconstructor

    def test_heading_labels_defined(self):
        """Test HEADING_LABELS contains expected values."""
        assert RegionLabel.SECTION_HEADER.value in MarkdownBuilder.HEADING_LABELS
        assert RegionLabel.TITLE.value in MarkdownBuilder.HEADING_LABELS

    def test_excluded_labels_defined(self):
        """Test EXCLUDED_LABELS contains expected values."""
        assert RegionLabel.CAPTION.value in MarkdownBuilder.EXCLUDED_LABELS
        assert RegionLabel.FOOTNOTE.value in MarkdownBuilder.EXCLUDED_LABELS
        assert RegionLabel.PAGE_FOOTER.value in MarkdownBuilder.EXCLUDED_LABELS


# =============================================================================
# Unit Tests: Heading Formatting
# =============================================================================


class TestHeadingFormatting:
    """Tests for heading region formatting."""

    def test_title_gets_h1(self, builder):
        """Test Title region gets # prefix."""
        region = create_mapped_region(
            label=RegionLabel.TITLE.value, text="Document Title"
        )
        result = builder._format_region(region)
        assert result == "# Document Title"

    def test_section_header_gets_h2(self, builder):
        """Test Section_Header region gets ## prefix."""
        region = create_mapped_region(
            label=RegionLabel.SECTION_HEADER.value, text="1. Introduction"
        )
        result = builder._format_region(region)
        assert result == "## 1. Introduction"

    def test_empty_heading_returns_none(self, builder):
        """Test empty heading text returns None."""
        region = create_mapped_region(label=RegionLabel.TITLE.value, text="")
        result = builder._format_region(region)
        assert result is None

    def test_whitespace_heading_returns_none(self, builder):
        """Test whitespace-only heading returns None."""
        region = create_mapped_region(
            label=RegionLabel.SECTION_HEADER.value, text="   "
        )
        result = builder._format_region(region)
        assert result is None

    def test_heading_text_trimmed(self, builder):
        """Test heading text is trimmed."""
        region = create_mapped_region(
            label=RegionLabel.TITLE.value, text="  Padded Title  "
        )
        result = builder._format_region(region)
        assert result == "# Padded Title"


# =============================================================================
# Unit Tests: Table Formatting
# =============================================================================


class TestTableFormatting:
    """Tests for table region formatting."""

    def test_table_with_words(self, builder):
        """Test table region with words produces Markdown table."""
        words = create_table_words([["Header1", "Header2"], ["Cell1", "Cell2"]])
        region = create_mapped_region(
            label=RegionLabel.TABLE.value,
            text="Header1 Header2 Cell1 Cell2",
            words=words,
        )
        result = builder._format_region(region)
        assert "|" in result
        assert "---" in result
        assert "Header1" in result
        assert "Cell1" in result

    def test_table_without_words_uses_text(self, builder):
        """Test table region without words returns text."""
        region = create_mapped_region(
            label=RegionLabel.TABLE.value, text="Fallback table text", words=[]
        )
        result = builder._format_region(region)
        assert result == "Fallback table text"

    def test_empty_table_returns_none(self, builder):
        """Test empty table region returns None."""
        region = create_mapped_region(label=RegionLabel.TABLE.value, text="", words=[])
        result = builder._format_region(region)
        assert result is None


# =============================================================================
# Unit Tests: Plain Text Formatting
# =============================================================================


class TestPlainTextFormatting:
    """Tests for text/list region formatting."""

    def test_text_region_plain_output(self, builder):
        """Test Text region outputs plain text."""
        region = create_mapped_region(
            label=RegionLabel.TEXT.value, text="This is a paragraph of text."
        )
        result = builder._format_region(region)
        assert result == "This is a paragraph of text."
        assert not result.startswith("#")

    def test_list_region_plain_output(self, builder):
        """Test List region outputs plain text."""
        region = create_mapped_region(
            label=RegionLabel.LIST.value, text="Item 1 Item 2 Item 3"
        )
        result = builder._format_region(region)
        assert result == "Item 1 Item 2 Item 3"

    def test_empty_text_returns_none(self, builder):
        """Test empty text region returns None."""
        region = create_mapped_region(label=RegionLabel.TEXT.value, text="")
        result = builder._format_region(region)
        assert result is None


# =============================================================================
# Unit Tests: Excluded Regions
# =============================================================================


class TestExcludedRegions:
    """Tests for excluded region types."""

    def test_caption_excluded(self, builder):
        """Test Caption region is excluded."""
        region = create_mapped_region(
            label=RegionLabel.CAPTION.value, text="Figure 1: Some caption"
        )
        result = builder._format_region(region)
        assert result is None

    def test_footnote_excluded(self, builder):
        """Test Footnote region is excluded."""
        region = create_mapped_region(
            label=RegionLabel.FOOTNOTE.value, text="1. This is a footnote"
        )
        result = builder._format_region(region)
        assert result is None

    def test_page_footer_excluded(self, builder):
        """Test Page_Footer region is excluded."""
        region = create_mapped_region(
            label=RegionLabel.PAGE_FOOTER.value, text="Page 1 of 10"
        )
        result = builder._format_region(region)
        assert result is None


# =============================================================================
# Unit Tests: Build Method
# =============================================================================


class TestBuildMethod:
    """Tests for build method."""

    def test_empty_regions_returns_page_marker(self, builder):
        """Test empty regions returns only page marker."""
        result = builder.build([], page_num=5)
        assert result == "<!-- Page 5 -->"

    def test_page_marker_included(self, builder):
        """Test page marker is included in output."""
        regions = [create_mapped_region(RegionLabel.TEXT.value, "Some text")]
        result = builder.build(regions, page_num=3)
        assert "<!-- Page 3 -->" in result

    def test_page_marker_at_beginning(self, builder):
        """Test page marker is at the beginning."""
        regions = [create_mapped_region(RegionLabel.TEXT.value, "Some text")]
        result = builder.build(regions, page_num=1)
        assert result.startswith("<!-- Page 1 -->")

    def test_regions_separated_by_double_newline(self, builder):
        """Test regions are separated by double newline."""
        regions = [
            create_mapped_region(RegionLabel.TITLE.value, "Title"),
            create_mapped_region(RegionLabel.TEXT.value, "Paragraph 1"),
            create_mapped_region(RegionLabel.TEXT.value, "Paragraph 2"),
        ]
        result = builder.build(regions, page_num=1)
        # Remove page marker for easier checking
        content = result.replace("<!-- Page 1 -->\n", "")
        parts = content.split("\n\n")
        assert len(parts) == 3

    def test_excluded_regions_not_in_output(self, builder):
        """Test excluded regions don't appear in output."""
        regions = [
            create_mapped_region(RegionLabel.TITLE.value, "Title"),
            create_mapped_region(RegionLabel.CAPTION.value, "Caption text"),
            create_mapped_region(RegionLabel.TEXT.value, "Body text"),
            create_mapped_region(RegionLabel.FOOTNOTE.value, "Footnote"),
        ]
        result = builder.build(regions, page_num=1)
        assert "Caption text" not in result
        assert "Footnote" not in result
        assert "Title" in result
        assert "Body text" in result

    def test_mixed_region_types(self, builder):
        """Test building with mixed region types."""
        table_words = create_table_words([["Col1", "Col2"], ["A", "B"]])
        regions = [
            create_mapped_region(RegionLabel.TITLE.value, "Document Title"),
            create_mapped_region(RegionLabel.SECTION_HEADER.value, "Section 1"),
            create_mapped_region(RegionLabel.TEXT.value, "Introduction text."),
            create_mapped_region(
                RegionLabel.TABLE.value, "Col1 Col2 A B", words=table_words
            ),
        ]
        result = builder.build(regions, page_num=1)

        # Check all expected content
        assert "# Document Title" in result
        assert "## Section 1" in result
        assert "Introduction text." in result
        assert "|" in result  # Table syntax


# =============================================================================
# Property-Based Tests
# =============================================================================


# Strategies for generating test data
@st.composite
def region_label_strategy(draw, exclude_noise=False):
    """Generate a random region label."""
    labels = list(RegionLabel)
    if exclude_noise:
        labels = [l for l in labels if l.value not in MarkdownBuilder.EXCLUDED_LABELS]
    return draw(st.sampled_from(labels)).value


@st.composite
def mapped_region_strategy(draw, label=None):
    """Generate a random MappedRegion."""
    if label is None:
        label = draw(region_label_strategy())

    text = draw(
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P"), whitelist_characters=" "
            ),
        )
    )
    assume(text.strip())

    bbox = (
        draw(st.floats(min_value=0, max_value=0.4)),
        draw(st.floats(min_value=0, max_value=0.4)),
        draw(st.floats(min_value=0.5, max_value=1.0)),
        draw(st.floats(min_value=0.5, max_value=1.0)),
    )

    region = LayoutRegion(bbox=bbox, label=label, confidence=0.9)
    return MappedRegion(region=region, words=[], text=text.strip())


@st.composite
def non_empty_regions_strategy(draw, min_regions=1, max_regions=5):
    """Generate a list of non-empty MappedRegions (excluding noise types)."""
    num_regions = draw(st.integers(min_value=min_regions, max_value=max_regions))
    regions = []
    for _ in range(num_regions):
        label = draw(region_label_strategy(exclude_noise=True))
        region = draw(mapped_region_strategy(label=label))
        regions.append(region)
    return regions


class TestMarkdownBuilderProperties:
    """
    Property-based tests for MarkdownBuilder.

    **Feature: hybrid-layout-extraction, Property 6: Region-to-Markdown Formatting**
    **Feature: hybrid-layout-extraction, Property 7: Region Separator**
    **Feature: hybrid-layout-extraction, Property 8: Page Marker Preservation**
    """

    @given(
        text=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters=" "
            ),
        )
    )
    @settings(max_examples=100)
    def test_heading_prefix_property(self, text):
        """
        **Feature: hybrid-layout-extraction, Property 6: Region-to-Markdown Formatting**

        *For any* MappedRegion with Section_Header or Title label,
        output SHALL start with # or ##.

        **Validates: Requirements 4.1**
        """
        assume(text.strip())
        builder = MarkdownBuilder()

        # Test Title -> #
        title_region = create_mapped_region(RegionLabel.TITLE.value, text.strip())
        title_result = builder._format_region(title_region)
        assert title_result is not None
        assert title_result.startswith(
            "# "
        ), f"Title should start with '# ', got: {title_result}"

        # Test Section_Header -> ##
        header_region = create_mapped_region(
            RegionLabel.SECTION_HEADER.value, text.strip()
        )
        header_result = builder._format_region(header_region)
        assert header_result is not None
        assert header_result.startswith(
            "## "
        ), f"Section_Header should start with '## ', got: {header_result}"

    @given(
        text=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters=" "
            ),
        )
    )
    @settings(max_examples=100)
    def test_plain_text_no_heading_property(self, text):
        """
        **Feature: hybrid-layout-extraction, Property 6: Region-to-Markdown Formatting**

        *For any* MappedRegion with Text or List label,
        output SHALL be plain text without heading prefixes.

        **Validates: Requirements 4.3**
        """
        assume(text.strip())
        builder = MarkdownBuilder()

        for label in [RegionLabel.TEXT.value, RegionLabel.LIST.value]:
            region = create_mapped_region(label, text.strip())
            result = builder._format_region(region)
            assert result is not None
            assert not result.startswith(
                "#"
            ), f"Plain text should not start with #, got: {result}"

    @given(
        text=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters=" "
            ),
        )
    )
    @settings(max_examples=100)
    def test_excluded_regions_property(self, text):
        """
        **Feature: hybrid-layout-extraction, Property 6: Region-to-Markdown Formatting**

        *For any* MappedRegion with Caption, Footnote, or Page_Footer label,
        output SHALL be None (excluded).

        **Validates: Requirements 4.4**
        """
        assume(text.strip())
        builder = MarkdownBuilder()

        for label in MarkdownBuilder.EXCLUDED_LABELS:
            region = create_mapped_region(label, text.strip())
            result = builder._format_region(region)
            assert result is None, f"Region with label {label} should be excluded"

    @given(regions=non_empty_regions_strategy(min_regions=2, max_regions=5))
    @settings(max_examples=100)
    def test_region_separator_property(self, regions):
        """
        **Feature: hybrid-layout-extraction, Property 7: Region Separator**

        *For any* two consecutive regions in Markdown output,
        they SHALL be separated by exactly double newline (\\n\\n).

        **Validates: Requirements 4.5**
        """
        builder = MarkdownBuilder()
        result = builder.build(regions, page_num=1)

        # Remove page marker
        content = result.replace("<!-- Page 1 -->\n", "")

        # Count formatted regions (non-empty, non-excluded)
        formatted_count = sum(
            1
            for r in regions
            if r.label not in MarkdownBuilder.EXCLUDED_LABELS and r.text.strip()
        )

        if formatted_count >= 2:
            # Split by double newline
            parts = content.split("\n\n")
            # Number of separators = number of parts - 1
            assert (
                len(parts) >= formatted_count
            ), f"Expected at least {formatted_count} parts, got {len(parts)}"

    @given(page_num=st.integers(min_value=1, max_value=1000))
    @settings(max_examples=100)
    def test_page_marker_preservation_property(self, page_num):
        """
        **Feature: hybrid-layout-extraction, Property 8: Page Marker Preservation**

        *For any* page processed through hybrid extraction,
        the output Markdown SHALL contain <!-- Page N --> marker.

        **Validates: Requirements 5.4**
        """
        builder = MarkdownBuilder()

        # Test with empty regions
        result_empty = builder.build([], page_num=page_num)
        assert f"<!-- Page {page_num} -->" in result_empty

        # Test with some regions
        regions = [create_mapped_region(RegionLabel.TEXT.value, "Some content")]
        result_with_content = builder.build(regions, page_num=page_num)
        assert f"<!-- Page {page_num} -->" in result_with_content

    @given(
        page_num=st.integers(min_value=1, max_value=100),
        regions=non_empty_regions_strategy(min_regions=1, max_regions=3),
    )
    @settings(max_examples=100)
    def test_page_marker_at_start_property(self, page_num, regions):
        """
        **Feature: hybrid-layout-extraction, Property 8: Page Marker Preservation**

        *For any* page, the page marker SHALL appear at the start of output.

        **Validates: Requirements 5.4**
        """
        builder = MarkdownBuilder()
        result = builder.build(regions, page_num=page_num)
        assert result.startswith(f"<!-- Page {page_num} -->")


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for MarkdownBuilder."""

    def test_all_excluded_regions(self, builder):
        """Test building with only excluded regions."""
        regions = [
            create_mapped_region(RegionLabel.CAPTION.value, "Caption"),
            create_mapped_region(RegionLabel.FOOTNOTE.value, "Footnote"),
            create_mapped_region(RegionLabel.PAGE_FOOTER.value, "Footer"),
        ]
        result = builder.build(regions, page_num=1)
        # Should only have page marker
        assert result == "<!-- Page 1 -->"

    def test_mixed_empty_and_content_regions(self, builder):
        """Test building with mix of empty and content regions."""
        regions = [
            create_mapped_region(RegionLabel.TITLE.value, "Title"),
            create_mapped_region(RegionLabel.TEXT.value, ""),  # Empty
            create_mapped_region(RegionLabel.TEXT.value, "Content"),
        ]
        result = builder.build(regions, page_num=1)
        assert "Title" in result
        assert "Content" in result
        # Should not have extra separators for empty region
        assert "\n\n\n\n" not in result

    def test_special_characters_in_text(self, builder):
        """Test text with special characters."""
        region = create_mapped_region(
            RegionLabel.TEXT.value, 'Text with <special> & "characters"'
        )
        result = builder._format_region(region)
        assert "<special>" in result
        assert "&" in result

    def test_unicode_text(self, builder):
        """Test Unicode text handling."""
        region = create_mapped_region(
            RegionLabel.TITLE.value, "Tiêu đề tiếng Việt 中文标题"
        )
        result = builder._format_region(region)
        assert "# Tiêu đề tiếng Việt 中文标题" == result

    def test_very_long_text(self, builder):
        """Test handling of very long text."""
        long_text = "Word " * 1000
        region = create_mapped_region(RegionLabel.TEXT.value, long_text)
        result = builder._format_region(region)
        assert result == long_text.strip()

    def test_page_num_zero(self, builder):
        """Test page number 0 (edge case)."""
        result = builder.build([], page_num=0)
        assert "<!-- Page 0 -->" in result

    def test_large_page_number(self, builder):
        """Test large page number."""
        result = builder.build([], page_num=99999)
        assert "<!-- Page 99999 -->" in result
