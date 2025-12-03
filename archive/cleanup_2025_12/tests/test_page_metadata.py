"""
Test suite for page metadata extraction and normalization
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.utils.page_utils import (
    calculate_page_coverage,
    extract_page_number,
    extract_page_range,
    format_page_citation,
    group_by_page_proximity,
    merge_page_ranges,
    normalize_page_metadata,
    validate_page_number,
)


class TestExtractPageNumber:
    """Test page number extraction with various metadata formats"""

    def test_direct_page_field(self):
        """Test extraction from direct page field"""
        metadata = {"page": 5}
        assert extract_page_number(metadata) == 5

    def test_page_start_field(self):
        """Test extraction from page_start field"""
        metadata = {"page_start": 10}
        assert extract_page_number(metadata) == 10

    def test_page_nums_list(self):
        """Test extraction from page_nums list"""
        metadata = {"page_nums": [3, 4, 5]}
        assert extract_page_number(metadata) == 3

    def test_page_num_field(self):
        """Test extraction from page_num field (alternative naming)"""
        metadata = {"page_num": 7}
        assert extract_page_number(metadata) == 7

    def test_chunk_id_extraction(self):
        """Test extraction from chunk_id containing page info"""
        metadata = {"chunk_id": "doc_chunk_5_page_12_abc123"}
        assert extract_page_number(metadata) == 12

        metadata = {"chunk_id": "chunk_page-8_xyz"}
        assert extract_page_number(metadata) == 8

    def test_empty_metadata(self):
        """Test with empty or None metadata"""
        assert extract_page_number({}) == 1
        assert extract_page_number(None) == 1

    def test_priority_order(self):
        """Test that page field has highest priority"""
        metadata = {
            "page": 5,
            "page_start": 10,
            "page_nums": [15],
            "page_num": 20,
            "chunk_id": "page_25",
        }
        assert extract_page_number(metadata) == 5

        # Without page field, page_start should win
        del metadata["page"]
        assert extract_page_number(metadata) == 10

        # Without page_start, page_nums should win
        del metadata["page_start"]
        assert extract_page_number(metadata) == 15


class TestValidatePageNumber:
    """Test page number validation and normalization"""

    def test_valid_integer(self):
        """Test with valid integer"""
        assert validate_page_number(5) == 5
        assert validate_page_number(100) == 100

    def test_float_conversion(self):
        """Test float to integer conversion"""
        assert validate_page_number(5.0) == 5
        assert validate_page_number(5.9) == 5

    def test_string_conversion(self):
        """Test string to integer conversion"""
        assert validate_page_number("5") == 5
        assert validate_page_number("10") == 10
        assert validate_page_number("page 15") == 15
        assert validate_page_number("p.20") == 20

    def test_invalid_values(self):
        """Test with invalid values"""
        assert validate_page_number(None) == 1
        assert validate_page_number("") == 1
        assert validate_page_number("abc") == 1
        assert validate_page_number([]) == 1

    def test_negative_and_zero(self):
        """Test that negative and zero values become 1"""
        assert validate_page_number(0) == 1
        assert validate_page_number(-5) == 1
        assert validate_page_number("-10") == 1


class TestNormalizePageMetadata:
    """Test metadata normalization"""

    def test_add_missing_page(self):
        """Test adding page field when missing"""
        metadata = {"doc_id": "test"}
        normalized = normalize_page_metadata(metadata)
        assert "page" in normalized
        assert normalized["page"] == 1

    def test_preserve_existing_page(self):
        """Test that existing page field is preserved"""
        metadata = {"page": 5, "doc_id": "test"}
        normalized = normalize_page_metadata(metadata)
        assert normalized["page"] == 5

    def test_page_from_page_start(self):
        """Test extracting page from page_start"""
        metadata = {"page_start": 10, "page_end": 12}
        normalized = normalize_page_metadata(metadata)
        assert normalized["page"] == 10
        assert normalized["page_end"] == 12  # Should be preserved

    def test_page_end_addition(self):
        """Test that page_end is added if only page_start exists"""
        metadata = {"page_start": 10}
        normalized = normalize_page_metadata(metadata)
        assert normalized["page"] == 10
        assert normalized["page_end"] == 10

    def test_none_metadata(self):
        """Test with None metadata"""
        normalized = normalize_page_metadata(None)
        assert isinstance(normalized, dict)
        assert normalized["page"] == 1


class TestExtractPageRange:
    """Test page range extraction"""

    def test_single_page(self):
        """Test with single page metadata"""
        metadata = {"page": 5}
        start, end = extract_page_range(metadata)
        assert start == 5
        assert end == 5

    def test_page_range(self):
        """Test with page range metadata"""
        metadata = {"page": 5, "page_end": 8}
        start, end = extract_page_range(metadata)
        assert start == 5
        assert end == 8

    def test_page_nums_range(self):
        """Test with page_nums list"""
        metadata = {"page_nums": [3, 4, 5, 6]}
        start, end = extract_page_range(metadata)
        assert start == 3
        assert end == 6

    def test_inconsistent_range(self):
        """Test that end is always >= start"""
        metadata = {"page": 10, "page_end": 5}
        start, end = extract_page_range(metadata)
        assert start == 10
        assert end == 10  # Should be corrected to match start


class TestMergePageRanges:
    """Test page range merging"""

    def test_non_overlapping(self):
        """Test with non-overlapping ranges"""
        ranges = [(1, 3), (5, 7), (10, 12)]
        merged = merge_page_ranges(ranges)
        assert merged == [(1, 3), (5, 7), (10, 12)]

    def test_overlapping(self):
        """Test with overlapping ranges"""
        ranges = [(1, 3), (2, 5), (4, 7)]
        merged = merge_page_ranges(ranges)
        assert merged == [(1, 7)]

    def test_consecutive(self):
        """Test with consecutive ranges"""
        ranges = [(1, 3), (4, 6), (7, 9)]
        merged = merge_page_ranges(ranges)
        assert merged == [(1, 9)]

    def test_mixed(self):
        """Test with mixed overlapping and non-overlapping"""
        ranges = [(1, 3), (2, 5), (7, 8), (8, 10), (15, 20)]
        merged = merge_page_ranges(ranges)
        assert merged == [(1, 5), (7, 10), (15, 20)]

    def test_empty(self):
        """Test with empty list"""
        assert merge_page_ranges([]) == []

    def test_unsorted_input(self):
        """Test with unsorted input"""
        ranges = [(10, 12), (1, 3), (4, 6)]
        merged = merge_page_ranges(ranges)
        assert merged == [(1, 6), (10, 12)]


class TestFormatPageCitation:
    """Test page citation formatting"""

    def test_single_page(self):
        """Test single page citation"""
        citation = format_page_citation("doc123", 5)
        assert citation == "doc123; p.5"

    def test_page_range(self):
        """Test page range citation"""
        citation = format_page_citation("doc123", (5, 8))
        assert citation == "doc123; pp.5-8"

    def test_single_page_range(self):
        """Test range with same start and end"""
        citation = format_page_citation("doc123", (5, 5))
        assert citation == "doc123; p.5"


class TestGroupByPageProximity:
    """Test grouping results by page proximity"""

    def test_single_document(self):
        """Test grouping within single document"""
        results = [
            {"doc_id": "doc1", "metadata": {"page": 1}},
            {"doc_id": "doc1", "metadata": {"page": 2}},
            {"doc_id": "doc1", "metadata": {"page": 5}},
            {"doc_id": "doc1", "metadata": {"page": 6}},
        ]
        groups = group_by_page_proximity(results, max_gap=1)
        assert len(groups) == 2
        assert len(groups[0]) == 2  # Pages 1-2
        assert len(groups[1]) == 2  # Pages 5-6

    def test_multiple_documents(self):
        """Test grouping across multiple documents"""
        results = [
            {"doc_id": "doc1", "metadata": {"page": 1}},
            {"doc_id": "doc2", "metadata": {"page": 1}},
            {"doc_id": "doc1", "metadata": {"page": 2}},
            {"doc_id": "doc2", "metadata": {"page": 3}},
        ]
        groups = group_by_page_proximity(results, max_gap=1)
        assert len(groups) == 3  # doc1: [1,2], doc2: [1], doc2: [3]

    def test_large_gap(self):
        """Test with large max_gap"""
        results = [
            {"doc_id": "doc1", "metadata": {"page": 1}},
            {"doc_id": "doc1", "metadata": {"page": 3}},
            {"doc_id": "doc1", "metadata": {"page": 5}},
        ]
        groups = group_by_page_proximity(results, max_gap=2)
        assert len(groups) == 1  # All should be grouped together


class TestCalculatePageCoverage:
    """Test page coverage statistics calculation"""

    def test_single_document(self):
        """Test coverage for single document"""
        results = [
            {"doc_id": "doc1", "metadata": {"page": 1}},
            {"doc_id": "doc1", "metadata": {"page": 3}},
            {"doc_id": "doc1", "metadata": {"page": 5}},
        ]
        stats = calculate_page_coverage(results)
        assert stats["total_pages_hit"] == 3
        assert stats["page_numbers"] == [1, 3, 5]
        assert "doc1" in stats["documents"]
        assert stats["documents"]["doc1"]["pages_hit"] == 3

    def test_multiple_documents(self):
        """Test coverage across multiple documents"""
        results = [
            {"doc_id": "doc1", "metadata": {"page": 1}},
            {"doc_id": "doc1", "metadata": {"page": 2}},
            {"doc_id": "doc2", "metadata": {"page": 5}},
            {"doc_id": "doc2", "metadata": {"page": 7}},
        ]
        stats = calculate_page_coverage(results)
        assert stats["total_pages_hit"] == 4
        assert stats["page_numbers"] == [1, 2, 5, 7]
        assert len(stats["documents"]) == 2
        assert stats["documents"]["doc1"]["pages_hit"] == 2
        assert stats["documents"]["doc2"]["pages_hit"] == 2

    def test_filtered_by_doc(self):
        """Test coverage filtered by specific document"""
        results = [
            {"doc_id": "doc1", "metadata": {"page": 1}},
            {"doc_id": "doc1", "metadata": {"page": 2}},
            {"doc_id": "doc2", "metadata": {"page": 5}},
        ]
        stats = calculate_page_coverage(results, doc_id="doc1")
        assert stats["total_pages_hit"] == 2
        assert stats["page_numbers"] == [1, 2]
        assert "doc1" in stats["documents"]
        assert "doc2" not in stats["documents"]


def test_integration_with_bm25_metadata():
    """Integration test with BM25-style metadata"""
    # Simulate BM25 metadata
    bm25_metadata = {
        "chunk_id": "doc_chunk_5",
        "doc_id": "report_2024",
        "page_start": 10,
        "page_end": 12,
        "heading": "Introduction",
        "level": 1,
    }

    # Normalize metadata
    normalized = normalize_page_metadata(bm25_metadata)

    # Check that page field was added
    assert "page" in normalized
    assert normalized["page"] == 10

    # Check that original fields are preserved
    assert normalized["page_start"] == 10
    assert normalized["page_end"] == 12
    assert normalized["doc_id"] == "report_2024"


def test_integration_with_faiss_metadata():
    """Integration test with FAISS-style metadata"""
    # Simulate FAISS metadata
    faiss_metadata = {
        "chunk_id": "chunk_123_page_5",
        "doc_id": "manual_v2",
        "page_nums": [5, 6],
        "doc_type": "pdf",
    }

    # Extract page number
    page = extract_page_number(faiss_metadata)
    assert page == 5

    # Normalize metadata
    normalized = normalize_page_metadata(faiss_metadata)
    assert normalized["page"] == 5
    assert normalized["page_nums"] == [5, 6]


def test_integration_with_text_chunk():
    """Integration test with TextChunk-style metadata"""
    # Simulate TextChunk metadata
    chunk_metadata = {
        "title": "User Manual",
        "author": "John Doe",
        "file_name": "manual.pdf",
    }
    page_nums = [3, 4]

    # Add page from page_nums
    if page_nums and "page" not in chunk_metadata:
        chunk_metadata["page"] = page_nums[0]

    # Normalize
    normalized = normalize_page_metadata(chunk_metadata)
    assert normalized["page"] == 3
    assert normalized["title"] == "User Manual"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
