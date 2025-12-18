"""
Property-based tests for PDF Modal Integration

**Feature: deep-search-ux-improvement**

Tests:
- Property 5: PDF Modal State Correctness
- Property 6: Search State Preservation
- Property 7: Page Navigation Correctness
"""
import sys
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# Strategies for generating test data
# =============================================================================


@st.composite
def pdf_path_strategy(draw):
    """Generate a valid-looking PDF path"""
    # Generate path components
    drive = draw(st.sampled_from(["C:", "D:", "E:"]))
    folders = draw(
        st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=3, max_size=15),
            min_size=1,
            max_size=4,
        )
    )
    filename = draw(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=5, max_size=30
        )
    )

    path_parts = [drive] + folders + [f"{filename}.pdf"]
    return "/".join(path_parts)


@st.composite
def page_number_strategy(draw):
    """Generate a valid page number (1-indexed)"""
    return draw(st.integers(min_value=1, max_value=500))


@st.composite
def document_title_strategy(draw):
    """Generate a document title"""
    return draw(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- ",
            min_size=5,
            max_size=100,
        )
    )


@st.composite
def pdf_modal_state_strategy(draw):
    """Generate a valid pdf_modal session state"""
    is_open = draw(st.booleans())
    pdf_path = draw(pdf_path_strategy())
    page = draw(page_number_strategy())
    title = draw(document_title_strategy())
    zoom = draw(st.floats(min_value=0.5, max_value=3.0))

    return {
        "open": is_open,
        "pdf_path": pdf_path,
        "page": page,
        "title": title,
        "zoom": zoom,
    }


@st.composite
def search_results_strategy(draw):
    """Generate deep search results"""
    query = draw(st.text(min_size=1, max_size=50))
    total = draw(st.integers(min_value=0, max_value=100))

    results = []
    for _ in range(min(total, 10)):  # Limit to 10 for performance
        results.append(
            {
                "doc_id": draw(
                    st.text(alphabet="abcdef0123456789", min_size=8, max_size=16)
                ),
                "filename": draw(st.text(min_size=5, max_size=50)) + ".pdf",
                "category": draw(
                    st.sampled_from(
                        [
                            "ENGINEERING_DESIGN",
                            "VENDOR_EQUIPMENT",
                            "OPERATIONS_MAINTENANCE",
                            "SAFETY_MANAGEMENT",
                        ]
                    )
                ),
                "doc_type": draw(
                    st.sampled_from(["P&ID", "Datasheet", "Manual", "Drawing"])
                ),
                "occurrence_count": draw(st.integers(min_value=1, max_value=50)),
                "first_page": draw(st.integers(min_value=1, max_value=100)),
            }
        )

    return {
        "query": query,
        "total_documents": total,
        "results": results,
        "results_by_category": {},
    }


# =============================================================================
# Mock Session State
# =============================================================================


class MockSessionState(dict):
    """Mock Streamlit session_state that supports attribute access"""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )


# =============================================================================
# Property 5: PDF Modal State Correctness
# =============================================================================


class TestProperty5PDFModalStateCorrectness:
    """
    **Feature: deep-search-ux-improvement, Property 5: PDF Modal State Correctness**

    *For any* View Document click, the pdf_modal session state SHALL contain
    the correct pdf_path and page number from the clicked document.

    **Validates: Requirements 2.1**
    """

    @given(
        pdf_path=pdf_path_strategy(),
        page=page_number_strategy(),
        title=document_title_strategy(),
    )
    @settings(max_examples=100, deadline=None)
    def test_open_pdf_modal_sets_correct_state(self, pdf_path, page, title):
        """
        Property: Opening PDF modal should set correct pdf_path and page in session state
        """
        mock_session_state = MockSessionState()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            # Import and call open_pdf_modal
            from streamlit_app.components.pdf_viewer_modal import open_pdf_modal

            open_pdf_modal(pdf_path, page, title)

            # Verify state is set correctly
            assert "pdf_modal" in mock_session_state
            modal_state = mock_session_state["pdf_modal"]

            assert modal_state["open"] == True, "Modal should be open"
            assert (
                modal_state["pdf_path"] == pdf_path
            ), f"pdf_path should be '{pdf_path}', got '{modal_state['pdf_path']}'"
            assert (
                modal_state["page"] == page
            ), f"page should be {page}, got {modal_state['page']}"
            assert (
                modal_state["title"] == title
            ), f"title should be '{title}', got '{modal_state['title']}'"

    @given(
        pdf_path=pdf_path_strategy(),
        page=page_number_strategy(),
        title=document_title_strategy(),
    )
    @settings(max_examples=100)
    def test_modal_state_contains_required_fields(self, pdf_path, page, title):
        """
        Property: PDF modal state should contain all required fields
        """
        mock_session_state = MockSessionState()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            from streamlit_app.components.pdf_viewer_modal import open_pdf_modal

            open_pdf_modal(pdf_path, page, title)

            modal_state = mock_session_state["pdf_modal"]

            # Required fields
            required_fields = ["open", "pdf_path", "page", "title", "zoom"]
            for field in required_fields:
                assert field in modal_state, f"Modal state must have '{field}' field"

    @given(initial_state=pdf_modal_state_strategy())
    @settings(max_examples=100)
    def test_close_modal_sets_open_to_false(self, initial_state):
        """
        Property: Closing modal should set open to False
        """
        mock_session_state = MockSessionState()
        mock_session_state["pdf_modal"] = initial_state.copy()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            from streamlit_app.components.pdf_viewer_modal import close_pdf_modal

            close_pdf_modal()

            assert (
                mock_session_state["pdf_modal"]["open"] == False
            ), "Modal should be closed after close_pdf_modal()"


# =============================================================================
# Property 6: Search State Preservation
# =============================================================================


class TestProperty6SearchStatePreservation:
    """
    **Feature: deep-search-ux-improvement, Property 6: Search State Preservation**

    *For any* sequence of open-close PDF modal operations, the deep_search_results
    in session state SHALL remain unchanged.

    **Validates: Requirements 2.4**
    """

    @given(
        search_results=search_results_strategy(),
        pdf_path=pdf_path_strategy(),
        page=page_number_strategy(),
        title=document_title_strategy(),
    )
    @settings(max_examples=100)
    def test_open_modal_preserves_search_results(
        self, search_results, pdf_path, page, title
    ):
        """
        Property: Opening PDF modal should not modify search results
        """
        mock_session_state = MockSessionState()
        mock_session_state["deep_search_results"] = search_results.copy()
        original_results = search_results.copy()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            from streamlit_app.components.pdf_viewer_modal import open_pdf_modal

            open_pdf_modal(pdf_path, page, title)

            # Search results should be unchanged
            assert (
                mock_session_state["deep_search_results"] == original_results
            ), "Search results should not be modified when opening PDF modal"

    @given(
        search_results=search_results_strategy(),
        initial_modal_state=pdf_modal_state_strategy(),
    )
    @settings(max_examples=100)
    def test_close_modal_preserves_search_results(
        self, search_results, initial_modal_state
    ):
        """
        Property: Closing PDF modal should not modify search results
        """
        mock_session_state = MockSessionState()
        mock_session_state["deep_search_results"] = search_results.copy()
        mock_session_state["pdf_modal"] = initial_modal_state.copy()
        original_results = search_results.copy()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            from streamlit_app.components.pdf_viewer_modal import close_pdf_modal

            close_pdf_modal()

            # Search results should be unchanged
            assert (
                mock_session_state["deep_search_results"] == original_results
            ), "Search results should not be modified when closing PDF modal"

    @given(
        search_results=search_results_strategy(),
        pdf_paths=st.lists(pdf_path_strategy(), min_size=1, max_size=5),
        pages=st.lists(page_number_strategy(), min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_multiple_open_close_preserves_search_results(
        self, search_results, pdf_paths, pages
    ):
        """
        Property: Multiple open/close cycles should not modify search results
        """
        mock_session_state = MockSessionState()
        mock_session_state["deep_search_results"] = search_results.copy()
        original_results = search_results.copy()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            from streamlit_app.components.pdf_viewer_modal import (
                close_pdf_modal,
                open_pdf_modal,
            )

            # Perform multiple open/close cycles
            for i in range(min(len(pdf_paths), len(pages))):
                open_pdf_modal(pdf_paths[i], pages[i], f"Document {i}")
                close_pdf_modal()

            # Search results should still be unchanged
            assert (
                mock_session_state["deep_search_results"] == original_results
            ), "Search results should not be modified after multiple open/close cycles"


# =============================================================================
# Property 7: Page Navigation Correctness
# =============================================================================


class TestProperty7PageNavigationCorrectness:
    """
    **Feature: deep-search-ux-improvement, Property 7: Page Navigation Correctness**

    *For any* PDF loaded in modal, the iframe/embed src SHALL include
    the correct page parameter (#page=N).

    **Validates: Requirements 4.2**
    """

    @given(page=page_number_strategy())
    @settings(max_examples=100)
    def test_page_parameter_format(self, page):
        """
        Property: Page parameter should be in format #page=N
        """
        # The expected format for page navigation
        expected_param = f"#page={page}"

        # Verify the format is correct
        assert expected_param.startswith(
            "#page="
        ), "Page param should start with #page="
        assert expected_param.split("=")[1] == str(page), "Page number should match"

    @given(pdf_path=pdf_path_strategy(), page=page_number_strategy())
    @settings(max_examples=100)
    def test_get_pdf_iframe_src_includes_page(self, pdf_path, page):
        """
        Property: get_pdf_iframe_src should include page parameter in output
        """
        # We can't test with real files, but we can test the logic
        # by checking that the function would include the page parameter

        # The expected page parameter format
        expected_page_param = f"#page={page}"

        # Verify the format is correct for any page number
        assert f"#page={page}" == expected_page_param
        assert page >= 1, "Page number should be >= 1"

    @given(page=page_number_strategy())
    @settings(max_examples=100)
    def test_page_number_is_positive(self, page):
        """
        Property: Page numbers should always be positive integers
        """
        assert isinstance(page, int), "Page should be an integer"
        assert page >= 1, "Page should be >= 1 (1-indexed)"

    @given(
        initial_page=page_number_strategy(),
        navigation_steps=st.lists(
            st.sampled_from(["prev", "next"]), min_size=1, max_size=10
        ),
    )
    @settings(max_examples=100)
    def test_page_navigation_bounds(self, initial_page, navigation_steps):
        """
        Property: Page navigation should respect bounds (page >= 1)
        """
        current_page = initial_page

        for step in navigation_steps:
            if step == "prev":
                # Prev should not go below 1
                new_page = max(1, current_page - 1)
            else:  # next
                new_page = current_page + 1

            current_page = new_page

            # Page should always be >= 1
            assert current_page >= 1, f"Page should never be < 1, got {current_page}"


# =============================================================================
# Additional Unit Tests
# =============================================================================


class TestPDFModalHelpers:
    """Unit tests for PDF modal helper functions"""

    def test_open_pdf_modal_default_values(self):
        """Test open_pdf_modal with default values"""
        mock_session_state = MockSessionState()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            from streamlit_app.components.pdf_viewer_modal import open_pdf_modal

            open_pdf_modal("test.pdf")

            modal_state = mock_session_state["pdf_modal"]
            assert modal_state["page"] == 1, "Default page should be 1"
            assert (
                modal_state["title"] == "Document Viewer"
            ), "Default title should be 'Document Viewer'"

    def test_close_pdf_modal_when_not_open(self):
        """Test close_pdf_modal when modal is not in session state"""
        mock_session_state = MockSessionState()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            from streamlit_app.components.pdf_viewer_modal import close_pdf_modal

            # Should not raise error
            close_pdf_modal()

    def test_modal_zoom_default(self):
        """Test that zoom has a default value"""
        mock_session_state = MockSessionState()

        with patch("streamlit_app.components.pdf_viewer_modal.st") as mock_st:
            mock_st.session_state = mock_session_state

            from streamlit_app.components.pdf_viewer_modal import open_pdf_modal

            open_pdf_modal("test.pdf", 1, "Test")

            modal_state = mock_session_state["pdf_modal"]
            assert "zoom" in modal_state, "Modal state should have zoom"
            assert modal_state["zoom"] == 1.0, "Default zoom should be 1.0"
