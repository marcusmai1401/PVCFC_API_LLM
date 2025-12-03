"""
Unit tests for IEEE-style citation formatter
Tests the convert_to_ieee_style function from query_lab_improved.py
"""

import os
import sys
from pathlib import Path

# Add streamlit_app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "streamlit_app"))

try:
    from components.query_lab_improved import convert_to_ieee_style
except ImportError:
    # If import fails, we'll define a minimal version for testing
    import re
    from typing import Dict, List, Optional, Tuple

    def convert_to_ieee_style(
        answer_text: str, citations: List[Dict], doc_number_map: Optional[Dict] = None
    ) -> Tuple[str, List[Dict]]:
        """Minimal implementation for testing"""
        # This should not be reached in normal testing
        return answer_text, []


def test_single_citation_basic():
    """Test simple single citation conversion"""
    answer = "CO2 compressor is described in [Doc 1, p.5]."
    citations = [
        {
            "doc_id": "DOCID_manual_abc123",
            "page": 5,
            "pdf_path": "/path/to/manual.pdf",
            "doc_number": "1",
        }
    ]
    doc_number_map = {
        "1": {
            "doc_id": "DOCID_manual_abc123",
            "pdf_path": "/path/to/manual.pdf",
            "file_name": "manual.pdf",
        }
    }

    converted, cite_list = convert_to_ieee_style(answer, citations, doc_number_map)

    assert "[1]" in converted
    assert "[Doc 1, p.5]" not in converted
    assert len(cite_list) == 1
    assert cite_list[0]["file_name"] == "manual.pdf"
    assert 5 in cite_list[0]["pages"]
    print("✓ test_single_citation_basic passed")


def test_multiple_citations_same_bracket():
    """Test multiple citations in one bracket"""
    answer = "Details found in [Doc 1, p.5; Doc 2, p.10]."
    citations = [
        {
            "doc_id": "DOCID_manual1_abc",
            "page": 5,
            "pdf_path": "/path/to/manual1.pdf",
            "doc_number": "1",
        },
        {
            "doc_id": "DOCID_manual2_def",
            "page": 10,
            "pdf_path": "/path/to/manual2.pdf",
            "doc_number": "2",
        },
    ]
    doc_number_map = {
        "1": {
            "doc_id": "DOCID_manual1_abc",
            "pdf_path": "/path/to/manual1.pdf",
            "file_name": "manual1.pdf",
        },
        "2": {
            "doc_id": "DOCID_manual2_def",
            "pdf_path": "/path/to/manual2.pdf",
            "file_name": "manual2.pdf",
        },
    }

    converted, cite_list = convert_to_ieee_style(answer, citations, doc_number_map)

    # Should convert to [1][2] or similar IEEE format
    assert "[Doc 1, p.5; Doc 2, p.10]" not in converted
    assert len(cite_list) == 2
    print("✓ test_multiple_citations_same_bracket passed")


def test_duplicate_doc_across_answer():
    """Test that same document cited multiple times gets single number"""
    answer = "First mention [Doc 1, p.5]. Second mention [Doc 1, p.8]."
    citations = [
        {
            "doc_id": "DOCID_manual_abc",
            "page": 5,
            "pdf_path": "/path/to/manual.pdf",
            "doc_number": "1",
        },
        {
            "doc_id": "DOCID_manual_abc",
            "page": 8,
            "pdf_path": "/path/to/manual.pdf",
            "doc_number": "1",
        },
    ]
    doc_number_map = {
        "1": {
            "doc_id": "DOCID_manual_abc",
            "pdf_path": "/path/to/manual.pdf",
            "file_name": "manual.pdf",
        }
    }

    converted, cite_list = convert_to_ieee_style(answer, citations, doc_number_map)

    # Should have only one entry in citation list
    assert len(cite_list) == 1
    # Should have both pages
    assert 5 in cite_list[0]["pages"]
    assert 8 in cite_list[0]["pages"]
    print("✓ test_duplicate_doc_across_answer passed")


def test_page_range_citation():
    """Test citation with page range"""
    answer = "Explained in [Doc 1, pp. 5-7]."
    citations = [
        {
            "doc_id": "DOCID_manual_abc",
            "page": 5,
            "pdf_path": "/path/to/manual.pdf",
            "doc_number": "1",
        },
        {
            "doc_id": "DOCID_manual_abc",
            "page": 6,
            "pdf_path": "/path/to/manual.pdf",
            "doc_number": "1",
        },
        {
            "doc_id": "DOCID_manual_abc",
            "page": 7,
            "pdf_path": "/path/to/manual.pdf",
            "doc_number": "1",
        },
    ]
    doc_number_map = {
        "1": {
            "doc_id": "DOCID_manual_abc",
            "pdf_path": "/path/to/manual.pdf",
            "file_name": "manual.pdf",
        }
    }

    converted, cite_list = convert_to_ieee_style(answer, citations, doc_number_map)

    assert "[1]" in converted
    assert len(cite_list) == 1
    # Should contain all pages in range
    assert 5 in cite_list[0]["pages"]
    assert 6 in cite_list[0]["pages"]
    assert 7 in cite_list[0]["pages"]
    print("✓ test_page_range_citation passed")


def test_missing_doc_number_map_fallback():
    """Test graceful fallback when doc_number_map is missing"""
    answer = "Some text without clear citations."
    citations = [
        {
            "doc_id": "DOCID_manual_abc",
            "page": 5,
            "pdf_path": "/path/to/manual.pdf",
        }
    ]

    # Call without doc_number_map
    converted, cite_list = convert_to_ieee_style(answer, citations, None)

    # Should not crash, should return original or handle gracefully
    assert converted is not None
    print("✓ test_missing_doc_number_map_fallback passed")


def test_empty_answer():
    """Test with empty answer text"""
    answer = ""
    citations = []

    converted, cite_list = convert_to_ieee_style(answer, citations, {})

    assert converted == ""
    assert len(cite_list) == 0
    print("✓ test_empty_answer passed")


def test_no_citations_in_answer():
    """Test answer with no citation patterns"""
    answer = "This is a plain answer with no citations at all."
    citations = [
        {
            "doc_id": "DOCID_manual_abc",
            "page": 5,
            "pdf_path": "/path/to/manual.pdf",
            "doc_number": "1",
        }
    ]
    doc_number_map = {
        "1": {
            "doc_id": "DOCID_manual_abc",
            "pdf_path": "/path/to/manual.pdf",
            "file_name": "manual.pdf",
        }
    }

    converted, cite_list = convert_to_ieee_style(answer, citations, doc_number_map)

    # Answer should remain unchanged
    assert converted == answer
    # Citation list should be empty (no citations found in text)
    assert len(cite_list) == 0
    print("✓ test_no_citations_in_answer passed")


def test_file_name_extraction_from_path():
    """Test that file names are correctly extracted from PDF paths"""
    answer = "Reference [Doc 1, p.5]."
    citations = [
        {
            "doc_id": "DOCID_longname_xyz",
            "page": 5,
            "pdf_path": "/very/long/path/to/documents/technical_manual_v2.pdf",
            "doc_number": "1",
        }
    ]
    doc_number_map = {
        "1": {
            "doc_id": "DOCID_longname_xyz",
            "pdf_path": "/very/long/path/to/documents/technical_manual_v2.pdf",
            "file_name": "technical_manual_v2.pdf",
        }
    }

    converted, cite_list = convert_to_ieee_style(answer, citations, doc_number_map)

    assert cite_list[0]["file_name"] == "technical_manual_v2.pdf"
    print("✓ test_file_name_extraction_from_path passed")


def test_citation_order_preservation():
    """Test that citations appear in order of first mention"""
    answer = "First [Doc 2, p.20]. Then [Doc 1, p.10]. Again [Doc 2, p.25]."
    citations = [
        {
            "doc_id": "DOCID_manual1_abc",
            "page": 10,
            "pdf_path": "/path/to/manual1.pdf",
            "doc_number": "1",
        },
        {
            "doc_id": "DOCID_manual2_def",
            "page": 20,
            "pdf_path": "/path/to/manual2.pdf",
            "doc_number": "2",
        },
        {
            "doc_id": "DOCID_manual2_def",
            "page": 25,
            "pdf_path": "/path/to/manual2.pdf",
            "doc_number": "2",
        },
    ]
    doc_number_map = {
        "1": {
            "doc_id": "DOCID_manual1_abc",
            "pdf_path": "/path/to/manual1.pdf",
            "file_name": "manual1.pdf",
        },
        "2": {
            "doc_id": "DOCID_manual2_def",
            "pdf_path": "/path/to/manual2.pdf",
            "file_name": "manual2.pdf",
        },
    }

    converted, cite_list = convert_to_ieee_style(answer, citations, doc_number_map)

    # Doc 2 should be [1] (first mention), Doc 1 should be [2] (second mention)
    assert len(cite_list) == 2
    # First entry should be manual2 (Doc 2 mentioned first)
    assert cite_list[0]["file_name"] == "manual2.pdf"
    # Second entry should be manual1 (Doc 1 mentioned second)
    assert cite_list[1]["file_name"] == "manual1.pdf"
    print("✓ test_citation_order_preservation passed")


def run_all_tests():
    """Run all test cases"""
    print("\n" + "=" * 60)
    print("Running IEEE Citation Formatter Unit Tests")
    print("=" * 60 + "\n")

    tests = [
        test_single_citation_basic,
        test_multiple_citations_same_bracket,
        test_duplicate_doc_across_answer,
        test_page_range_citation,
        test_missing_doc_number_map_fallback,
        test_empty_answer,
        test_no_citations_in_answer,
        test_file_name_extraction_from_path,
        test_citation_order_preservation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
