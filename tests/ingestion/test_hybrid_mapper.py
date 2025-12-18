"""
Unit tests and property tests for HybridMapper.

Tests cover:
- Property 2: Word-to-Region Assignment
- Property 3: Reading Order Sorting
- IoU calculation accuracy
- Edge cases and error handling

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.ingestion.layout import (
    GCVWord,
    HybridMapper,
    LayoutRegion,
    MappedRegion,
    RegionLabel,
)

# =============================================================================
# Hypothesis Strategies
# =============================================================================


def valid_bbox_strategy():
    """Generate valid bounding boxes where x0 < x1 and y0 < y1."""
    return st.tuples(
        st.floats(min_value=0, max_value=0.49),  # x0
        st.floats(min_value=0, max_value=0.49),  # y0
        st.floats(min_value=0.5, max_value=1.0),  # x1
        st.floats(min_value=0.5, max_value=1.0),  # y1
    )


def pixel_bbox_strategy(max_coord: int = 1000):
    """Generate valid pixel bounding boxes."""
    return st.tuples(
        st.floats(min_value=0, max_value=max_coord * 0.49),  # x0
        st.floats(min_value=0, max_value=max_coord * 0.49),  # y0
        st.floats(min_value=max_coord * 0.5, max_value=max_coord),  # x1
        st.floats(min_value=max_coord * 0.5, max_value=max_coord),  # y1
    )


def gcv_word_strategy():
    """Generate random GCVWord objects."""
    return st.builds(
        GCVWord,
        text=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters=" "
            ),
        ),
        bbox=pixel_bbox_strategy(1000),
    )


def layout_region_strategy():
    """Generate random LayoutRegion objects."""
    return st.builds(
        LayoutRegion,
        bbox=valid_bbox_strategy(),
        label=st.sampled_from(RegionLabel.get_all_values()),
        confidence=st.floats(min_value=0, max_value=1),
    )


# =============================================================================
# Unit Tests for IoU Calculation
# =============================================================================


class TestIoUCalculation:
    """Tests for _calculate_overlap method."""

    def test_complete_overlap(self):
        """Test word completely inside region returns 1.0."""
        mapper = HybridMapper()

        word_bbox = (0.3, 0.3, 0.4, 0.4)  # Small word
        region_bbox = (0.1, 0.1, 0.9, 0.9)  # Large region

        overlap = mapper._calculate_overlap(word_bbox, region_bbox)

        assert overlap == pytest.approx(1.0, rel=1e-6)

    def test_no_overlap(self):
        """Test non-overlapping boxes return 0.0."""
        mapper = HybridMapper()

        word_bbox = (0.1, 0.1, 0.2, 0.2)
        region_bbox = (0.5, 0.5, 0.9, 0.9)

        overlap = mapper._calculate_overlap(word_bbox, region_bbox)

        assert overlap == 0.0

    def test_partial_overlap(self):
        """Test partial overlap returns correct percentage."""
        mapper = HybridMapper()

        # Word: 0.2 x 0.2 = 0.04 area
        word_bbox = (0.4, 0.4, 0.6, 0.6)
        # Region covers half of word horizontally
        region_bbox = (0.5, 0.0, 1.0, 1.0)

        # Intersection: 0.1 x 0.2 = 0.02
        # Overlap = 0.02 / 0.04 = 0.5
        overlap = mapper._calculate_overlap(word_bbox, region_bbox)

        assert overlap == pytest.approx(0.5, rel=1e-6)

    def test_zero_area_word(self):
        """Test zero-area word returns 0.0."""
        mapper = HybridMapper()

        word_bbox = (0.5, 0.5, 0.5, 0.5)  # Zero area
        region_bbox = (0.1, 0.1, 0.9, 0.9)

        overlap = mapper._calculate_overlap(word_bbox, region_bbox)

        assert overlap == 0.0


# =============================================================================
# Unit Tests for Word-to-Region Assignment
# =============================================================================


class TestWordToRegionAssignment:
    """Tests for map_words_to_regions method."""

    def test_word_assigned_to_high_overlap_region(self):
        """
        **Feature: hybrid-layout-extraction, Property 2: Word-to-Region Assignment**

        Test that word with >60% overlap is assigned to that region.
        **Validates: Requirements 2.1**
        """
        mapper = HybridMapper(iou_threshold=0.6)

        # Word at (100, 100) to (200, 200) in 1000x1000 page
        # Normalized: (0.1, 0.1, 0.2, 0.2)
        word = GCVWord(text="test", bbox=(100, 100, 200, 200))

        # Region covers the word completely
        region = LayoutRegion(
            bbox=(0.05, 0.05, 0.25, 0.25), label=RegionLabel.TEXT.value, confidence=0.9
        )

        result = mapper.map_words_to_regions(
            words=[word], regions=[region], page_width=1000, page_height=1000
        )

        assert len(result) == 1
        assert len(result[0].words) == 1
        assert result[0].words[0].text == "test"

    def test_word_assigned_to_highest_overlap_region(self):
        """
        **Feature: hybrid-layout-extraction, Property 2: Word-to-Region Assignment**

        Test that word overlapping multiple regions goes to highest overlap.
        **Validates: Requirements 2.2**
        """
        mapper = HybridMapper(iou_threshold=0.6)

        # Word at center
        word = GCVWord(text="test", bbox=(400, 400, 600, 600))

        # Region 1: covers 70% of word
        region1 = LayoutRegion(
            bbox=(0.35, 0.35, 0.55, 0.65), label=RegionLabel.TEXT.value, confidence=0.9
        )

        # Region 2: covers 90% of word
        region2 = LayoutRegion(
            bbox=(0.38, 0.38, 0.62, 0.62),
            label=RegionLabel.SECTION_HEADER.value,
            confidence=0.9,
        )

        result = mapper.map_words_to_regions(
            words=[word], regions=[region1, region2], page_width=1000, page_height=1000
        )

        # Word should be in region2 (higher overlap)
        region2_result = [
            r for r in result if r.label == RegionLabel.SECTION_HEADER.value
        ][0]
        assert len(region2_result.words) == 1

    def test_unmatched_word_goes_to_default_text_region(self):
        """
        **Feature: hybrid-layout-extraction, Property 2: Word-to-Region Assignment**

        Test that word with <60% overlap goes to default Text region.
        **Validates: Requirements 2.3**
        """
        mapper = HybridMapper(iou_threshold=0.6)

        # Word at bottom right
        word = GCVWord(text="orphan", bbox=(800, 800, 900, 900))

        # Region at top left - no overlap
        region = LayoutRegion(
            bbox=(0.0, 0.0, 0.3, 0.3),
            label=RegionLabel.SECTION_HEADER.value,
            confidence=0.9,
        )

        result = mapper.map_words_to_regions(
            words=[word], regions=[region], page_width=1000, page_height=1000
        )

        # Should have 2 regions: original + default Text
        assert len(result) == 2

        # Find the default Text region
        default_region = [r for r in result if r.label == RegionLabel.TEXT.value][0]
        assert len(default_region.words) == 1
        assert default_region.words[0].text == "orphan"

    def test_empty_words_returns_empty_regions(self):
        """Test that empty word list returns regions with no words."""
        mapper = HybridMapper()

        region = LayoutRegion(
            bbox=(0.1, 0.1, 0.9, 0.9), label=RegionLabel.TEXT.value, confidence=0.9
        )

        result = mapper.map_words_to_regions(
            words=[], regions=[region], page_width=1000, page_height=1000
        )

        assert len(result) == 1
        assert len(result[0].words) == 0

    def test_invalid_page_dimensions_raises_error(self):
        """Test that invalid page dimensions raise ValueError."""
        mapper = HybridMapper()

        word = GCVWord(text="test", bbox=(100, 100, 200, 200))
        region = LayoutRegion(bbox=(0.1, 0.1, 0.9, 0.9), label="Text")

        with pytest.raises(ValueError):
            mapper.map_words_to_regions(
                words=[word], regions=[region], page_width=0, page_height=1000
            )


# =============================================================================
# Unit Tests for Reading Order
# =============================================================================


class TestReadingOrder:
    """Tests for _sort_by_reading_order method."""

    def test_sort_by_y_then_x(self):
        """
        **Feature: hybrid-layout-extraction, Property 3: Reading Order Sorting**

        Test that words are sorted by Y ascending, then X ascending.
        **Validates: Requirements 2.4**
        """
        mapper = HybridMapper()

        # Words in random order
        words = [
            GCVWord(text="bottom_right", bbox=(500, 500, 600, 550)),
            GCVWord(text="top_left", bbox=(100, 100, 200, 150)),
            GCVWord(text="top_right", bbox=(500, 100, 600, 150)),
            GCVWord(text="bottom_left", bbox=(100, 500, 200, 550)),
        ]

        sorted_words = mapper._sort_by_reading_order(words)

        # Expected order: top_left, top_right, bottom_left, bottom_right
        assert sorted_words[0].text == "top_left"
        assert sorted_words[1].text == "top_right"
        assert sorted_words[2].text == "bottom_left"
        assert sorted_words[3].text == "bottom_right"

    def test_same_y_sorted_by_x(self):
        """Test words on same line are sorted by X."""
        mapper = HybridMapper()

        words = [
            GCVWord(text="third", bbox=(300, 100, 400, 150)),
            GCVWord(text="first", bbox=(100, 100, 200, 150)),
            GCVWord(text="second", bbox=(200, 100, 300, 150)),
        ]

        sorted_words = mapper._sort_by_reading_order(words)

        assert sorted_words[0].text == "first"
        assert sorted_words[1].text == "second"
        assert sorted_words[2].text == "third"


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestHybridMapperProperties:
    """Property-based tests for HybridMapper."""

    @settings(max_examples=100)
    @given(
        words=st.lists(gcv_word_strategy(), min_size=1, max_size=20),
        regions=st.lists(layout_region_strategy(), min_size=1, max_size=5),
    )
    def test_all_words_assigned_property(self, words, regions):
        """
        **Feature: hybrid-layout-extraction, Property 2: Word-to-Region Assignment**

        For any set of words and regions, every word SHALL be assigned to
        exactly one region (either a detected region or default Text region).
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        mapper = HybridMapper(iou_threshold=0.6)

        result = mapper.map_words_to_regions(
            words=words, regions=regions, page_width=1000, page_height=1000
        )

        # Count total words in all regions
        total_assigned = sum(len(r.words) for r in result)

        # All words should be assigned
        assert total_assigned == len(
            words
        ), f"Expected {len(words)} words assigned, got {total_assigned}"

    @settings(max_examples=100)
    @given(words=st.lists(gcv_word_strategy(), min_size=2, max_size=20))
    def test_reading_order_property(self, words):
        """
        **Feature: hybrid-layout-extraction, Property 3: Reading Order Sorting**

        For any list of words, the sorted output SHALL have words ordered
        by Y-coordinate ascending, then X-coordinate ascending.
        **Validates: Requirements 2.4**
        """
        mapper = HybridMapper()

        sorted_words = mapper._sort_by_reading_order(words)

        # Verify ordering
        for i in range(len(sorted_words) - 1):
            curr = sorted_words[i]
            next_word = sorted_words[i + 1]

            # Y should be ascending
            assert (
                curr.bbox[1] <= next_word.bbox[1]
            ), f"Word {i} Y ({curr.bbox[1]}) > Word {i+1} Y ({next_word.bbox[1]})"

            # If same Y, X should be ascending
            if curr.bbox[1] == next_word.bbox[1]:
                assert (
                    curr.bbox[0] <= next_word.bbox[0]
                ), f"Same Y but Word {i} X ({curr.bbox[0]}) > Word {i+1} X ({next_word.bbox[0]})"

    @settings(max_examples=100)
    @given(word_bbox=valid_bbox_strategy(), region_bbox=valid_bbox_strategy())
    def test_overlap_range_property(self, word_bbox, region_bbox):
        """
        **Feature: hybrid-layout-extraction, Property 2: Word-to-Region Assignment**

        For any word and region bounding boxes, the overlap percentage
        SHALL be in the range [0, 1].
        **Validates: Requirements 2.1**
        """
        mapper = HybridMapper()

        overlap = mapper._calculate_overlap(word_bbox, region_bbox)

        assert 0 <= overlap <= 1, f"Overlap {overlap} not in [0, 1]"

    @settings(max_examples=100)
    @given(
        threshold=st.floats(min_value=0.01, max_value=0.99),
        words=st.lists(gcv_word_strategy(), min_size=1, max_size=10),
        regions=st.lists(layout_region_strategy(), min_size=1, max_size=3),
    )
    def test_threshold_respected_property(self, threshold, words, regions):
        """
        **Feature: hybrid-layout-extraction, Property 2: Word-to-Region Assignment**

        For any IoU threshold, words assigned to detected regions SHALL
        have overlap >= threshold with that region.
        **Validates: Requirements 2.1**
        """
        mapper = HybridMapper(iou_threshold=threshold)

        result = mapper.map_words_to_regions(
            words=words, regions=regions, page_width=1000, page_height=1000
        )

        # For each word in a detected region (not default), verify overlap
        for mapped_region in result:
            # Skip default Text regions (confidence=0)
            if mapped_region.region.confidence == 0:
                continue

            for word in mapped_region.words:
                word_bbox_norm = mapper._normalize_bbox(word.bbox, 1000, 1000)
                overlap = mapper._calculate_overlap(
                    word_bbox_norm, mapped_region.region.bbox
                )

                assert (
                    overlap >= threshold
                ), f"Word assigned with overlap {overlap} < threshold {threshold}"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_word_single_region(self):
        """Test simplest case: one word, one region."""
        mapper = HybridMapper()

        word = GCVWord(text="hello", bbox=(100, 100, 200, 150))
        region = LayoutRegion(
            bbox=(0.0, 0.0, 1.0, 1.0),  # Full page
            label=RegionLabel.TEXT.value,
            confidence=0.9,
        )

        result = mapper.map_words_to_regions(
            words=[word], regions=[region], page_width=1000, page_height=1000
        )

        assert len(result) == 1
        assert result[0].text == "hello"

    def test_multiple_words_same_region(self):
        """Test multiple words assigned to same region."""
        mapper = HybridMapper()

        words = [
            GCVWord(text="hello", bbox=(100, 100, 200, 150)),
            GCVWord(text="world", bbox=(210, 100, 310, 150)),
        ]

        region = LayoutRegion(
            bbox=(0.0, 0.0, 1.0, 1.0), label=RegionLabel.TEXT.value, confidence=0.9
        )

        result = mapper.map_words_to_regions(
            words=words, regions=[region], page_width=1000, page_height=1000
        )

        assert len(result) == 1
        assert result[0].word_count == 2
        assert result[0].text == "hello world"

    def test_words_distributed_across_regions(self):
        """Test words correctly distributed to different regions."""
        mapper = HybridMapper()

        # Word in top region
        word1 = GCVWord(text="header", bbox=(100, 50, 200, 100))
        # Word in bottom region
        word2 = GCVWord(text="content", bbox=(100, 600, 200, 650))

        # Top region
        region1 = LayoutRegion(
            bbox=(0.0, 0.0, 1.0, 0.2),
            label=RegionLabel.SECTION_HEADER.value,
            confidence=0.9,
        )
        # Bottom region
        region2 = LayoutRegion(
            bbox=(0.0, 0.5, 1.0, 1.0), label=RegionLabel.TEXT.value, confidence=0.9
        )

        result = mapper.map_words_to_regions(
            words=[word1, word2],
            regions=[region1, region2],
            page_width=1000,
            page_height=1000,
        )

        header_region = [
            r for r in result if r.label == RegionLabel.SECTION_HEADER.value
        ][0]
        text_region = [r for r in result if r.label == RegionLabel.TEXT.value][0]

        assert header_region.text == "header"
        assert text_region.text == "content"

    def test_iou_threshold_validation(self):
        """Test that invalid IoU threshold raises error."""
        with pytest.raises(ValueError):
            HybridMapper(iou_threshold=0)

        with pytest.raises(ValueError):
            HybridMapper(iou_threshold=1.5)

        with pytest.raises(ValueError):
            HybridMapper(iou_threshold=-0.1)
