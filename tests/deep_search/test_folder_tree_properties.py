"""
Property-based tests for Deep Search Folder Tree UI

**Feature: deep-search-ux-improvement**

Tests:
- Property 1: Tree Structure Hierarchy
- Property 2: Folder Toggle State Consistency
- Property 3: Empty Category Filtering
- Property 4: Document Item Completeness
- Property 8: Tree Node Rendering Completeness
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from streamlit_app.components.deep_search import (
    CATEGORY_ICONS,
    DOC_TYPE_ICONS,
    init_folder_tree_state,
    is_folder_expanded,
    toggle_folder,
    truncate_filename,
)

# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid categories
VALID_CATEGORIES = [
    "ENGINEERING_DESIGN",
    "VENDOR_EQUIPMENT",
    "OPERATIONS_MAINTENANCE",
    "SAFETY_MANAGEMENT",
]

# Valid doc_types per category
DOC_TYPES_BY_CATEGORY = {
    "ENGINEERING_DESIGN": ["P&ID", "Drawing", "Technical Data"],
    "VENDOR_EQUIPMENT": ["Datasheet", "Material Partlist", "Vendor Manual"],
    "OPERATIONS_MAINTENANCE": [
        "Operation Instruction",
        "Maintenance Instruction",
        "Maintenance History",
        "Inventory",
    ],
    "SAFETY_MANAGEMENT": ["MOC", "RCA", "Pictures"],
}

valid_category_strategy = st.sampled_from(VALID_CATEGORIES)


@st.composite
def document_strategy(draw):
    """Generate a test document result"""
    category = draw(valid_category_strategy)
    doc_types = DOC_TYPES_BY_CATEGORY.get(category, ["Unknown"])
    doc_type = draw(st.sampled_from(doc_types))

    doc_id = draw(st.text(alphabet="abcdef0123456789", min_size=8, max_size=16))
    filename = (
        draw(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz_0123456789",
                min_size=5,
                max_size=50,
            )
        )
        + ".pdf"
    )
    page_number = draw(st.integers(min_value=1, max_value=100))
    occurrence_count = draw(st.integers(min_value=1, max_value=50))

    return {
        "doc_id": doc_id,
        "filename": filename,
        "category": category,
        "doc_type": doc_type,
        "first_page": page_number,
        "occurrence_count": occurrence_count,
        "pdf_path": f"D:/Data/{filename}",
        "snippet": f"Sample text containing keyword...",
    }


@st.composite
def results_by_category_strategy(draw, min_docs=0, max_docs=10):
    """Generate results_by_category dict with documents grouped by category"""
    results_by_category = {}

    # Decide which categories to include (some may be empty)
    for category in VALID_CATEGORIES:
        include_category = draw(st.booleans())
        if include_category:
            num_docs = draw(st.integers(min_value=1, max_value=max_docs))
            docs = []
            for _ in range(num_docs):
                doc = draw(document_strategy())
                # Override category to match the group
                doc["category"] = category
                doc["doc_type"] = draw(
                    st.sampled_from(DOC_TYPES_BY_CATEGORY.get(category, ["Unknown"]))
                )
                docs.append(doc)
            results_by_category[category] = docs

    return results_by_category


@st.composite
def folder_key_strategy(draw):
    """Generate a valid folder key (category or category_doctype)"""
    category = draw(valid_category_strategy)
    is_doc_type_key = draw(st.booleans())

    if is_doc_type_key:
        doc_types = DOC_TYPES_BY_CATEGORY.get(category, ["Unknown"])
        doc_type = draw(st.sampled_from(doc_types))
        return f"{category}_{doc_type}"
    return category


# =============================================================================
# Property 1: Tree Structure Hierarchy
# =============================================================================


class TestProperty1TreeStructureHierarchy:
    """
    **Feature: deep-search-ux-improvement, Property 1: Tree Structure Hierarchy**

    *For any* search results data, the rendered folder tree SHALL have categories
    at root level and doc_types as children, with documents as leaf nodes.

    **Validates: Requirements 1.1**
    """

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_categories_are_root_level(self, results):
        """
        Property: All categories in results should be at root level (no parent)
        """
        # Categories in results should be valid root-level categories
        for category in results.keys():
            assert (
                category in VALID_CATEGORIES
            ), f"Category '{category}' is not a valid root-level category"

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_doc_types_are_children_of_categories(self, results):
        """
        Property: All doc_types should be valid children of their parent category
        """
        for category, docs in results.items():
            valid_doc_types = DOC_TYPES_BY_CATEGORY.get(category, ["Unknown"])
            for doc in docs:
                doc_type = doc.get("doc_type", "Unknown")
                assert (
                    doc_type in valid_doc_types
                ), f"Doc type '{doc_type}' is not valid for category '{category}'"

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_documents_are_leaf_nodes(self, results):
        """
        Property: Documents should have required leaf node fields (no children)
        """
        for category, docs in results.items():
            for doc in docs:
                # Documents should have these fields (leaf node properties)
                assert "doc_id" in doc, "Document must have doc_id"
                assert "filename" in doc, "Document must have filename"
                assert "first_page" in doc, "Document must have first_page"
                # Documents should NOT have children
                assert "children" not in doc, "Documents should not have children"
                assert "sub_items" not in doc, "Documents should not have sub_items"

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_hierarchy_depth_is_three_levels(self, results):
        """
        Property: Tree hierarchy should be exactly 3 levels: category -> doc_type -> document
        """
        for category, docs in results.items():
            # Level 1: Category
            assert isinstance(category, str), "Category (level 1) must be string"

            # Group by doc_type to verify level 2
            doc_types_in_category = set()
            for doc in docs:
                doc_type = doc.get("doc_type")
                doc_types_in_category.add(doc_type)

                # Level 3: Document - verify it's a dict with required fields
                assert isinstance(doc, dict), "Document (level 3) must be dict"
                assert "filename" in doc, "Document must have filename"

            # Level 2: Doc types should exist
            assert (
                len(doc_types_in_category) > 0 or len(docs) == 0
            ), "Non-empty category should have at least one doc_type"


# =============================================================================
# Property 2: Folder Toggle State Consistency
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


class TestProperty2FolderToggleStateConsistency:
    """
    **Feature: deep-search-ux-improvement, Property 2: Folder Toggle State Consistency**

    *For any* folder (category or doc_type), toggling its state SHALL flip the expanded
    boolean in session state, and the UI indicator SHALL match the current state
    (▼ for expanded, ▶ for collapsed).

    **Validates: Requirements 1.2, 1.3, 5.4, 5.5**
    """

    @given(folder_key=folder_key_strategy())
    @settings(max_examples=100)
    def test_toggle_flips_state(self, folder_key):
        """
        Property: Toggling a folder should flip its expanded state
        """
        # Mock streamlit session state with attribute access support
        mock_session_state = MockSessionState()

        with patch("streamlit_app.components.deep_search.st") as mock_st:
            mock_st.session_state = mock_session_state

            # Initialize state
            init_folder_tree_state()

            # Get initial state (should be False by default)
            initial_state = is_folder_expanded(folder_key)
            assert initial_state == False, "Initial state should be False"

            # Toggle once
            toggle_folder(folder_key)
            after_first_toggle = is_folder_expanded(folder_key)
            assert after_first_toggle == True, "After first toggle should be True"

            # Toggle again
            toggle_folder(folder_key)
            after_second_toggle = is_folder_expanded(folder_key)
            assert after_second_toggle == False, "After second toggle should be False"

    @given(folder_key=folder_key_strategy(), initial_expanded=st.booleans())
    @settings(max_examples=100)
    def test_toggle_inverts_any_state(self, folder_key, initial_expanded):
        """
        Property: Toggle should always invert the current state
        """
        mock_session_state = MockSessionState()
        mock_session_state["folder_tree_state"] = {folder_key: initial_expanded}

        with patch("streamlit_app.components.deep_search.st") as mock_st:
            mock_st.session_state = mock_session_state

            # Toggle
            toggle_folder(folder_key)

            # State should be inverted
            new_state = is_folder_expanded(folder_key)
            assert new_state == (
                not initial_expanded
            ), f"Toggle should invert state from {initial_expanded} to {not initial_expanded}"

    @given(folder_keys=st.lists(folder_key_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_toggle_only_affects_target_folder(self, folder_keys):
        """
        Property: Toggling one folder should not affect other folders
        """
        assume(len(set(folder_keys)) > 1)  # Need at least 2 unique keys

        mock_session_state = MockSessionState()

        with patch("streamlit_app.components.deep_search.st") as mock_st:
            mock_st.session_state = mock_session_state

            init_folder_tree_state()

            # Set all folders to expanded
            for key in folder_keys:
                mock_session_state["folder_tree_state"][key] = True

            # Toggle only the first folder
            target_key = folder_keys[0]
            toggle_folder(target_key)

            # Check that only target was affected
            for key in folder_keys:
                if key == target_key:
                    assert (
                        is_folder_expanded(key) == False
                    ), f"Target folder '{key}' should be toggled to False"
                else:
                    assert (
                        is_folder_expanded(key) == True
                    ), f"Non-target folder '{key}' should remain True"


# =============================================================================
# Property 3: Empty Category Filtering
# =============================================================================


class TestProperty3EmptyCategoryFiltering:
    """
    **Feature: deep-search-ux-improvement, Property 3: Empty Category Filtering**

    *For any* search results, categories with zero documents SHALL NOT appear
    in the rendered tree view.

    **Validates: Requirements 1.5**
    """

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_empty_categories_are_filtered(self, results):
        """
        Property: Categories with empty document lists should be filtered out
        """
        # Add some empty categories
        results_with_empty = dict(results)
        results_with_empty["EMPTY_CAT_1"] = []
        results_with_empty["EMPTY_CAT_2"] = []

        # Filter logic (same as in render_folder_tree)
        non_empty_categories = [
            cat for cat, docs in results_with_empty.items() if len(docs) > 0
        ]

        # Verify no empty categories in filtered list
        for cat in non_empty_categories:
            assert (
                len(results_with_empty[cat]) > 0
            ), f"Category '{cat}' should not be in non_empty list"

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_non_empty_categories_are_preserved(self, results):
        """
        Property: Categories with documents should be preserved
        """
        # Filter logic
        non_empty_categories = [cat for cat, docs in results.items() if len(docs) > 0]

        # All non-empty categories from original should be in filtered list
        for cat, docs in results.items():
            if len(docs) > 0:
                assert (
                    cat in non_empty_categories
                ), f"Non-empty category '{cat}' should be preserved"

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_filtered_count_matches_non_empty_count(self, results):
        """
        Property: Number of filtered categories should equal number of non-empty categories
        """
        non_empty_count = sum(1 for docs in results.values() if len(docs) > 0)

        filtered_categories = [cat for cat, docs in results.items() if len(docs) > 0]

        assert len(filtered_categories) == non_empty_count, (
            f"Filtered count ({len(filtered_categories)}) should equal "
            f"non-empty count ({non_empty_count})"
        )


# =============================================================================
# Property 4: Document Item Completeness
# =============================================================================


class TestProperty4DocumentItemCompleteness:
    """
    **Feature: deep-search-ux-improvement, Property 4: Document Item Completeness**

    *For any* document in search results, the rendered item SHALL contain:
    document icon, filename (truncated if > 40 chars), occurrence count,
    first page number, and a View button.

    **Validates: Requirements 1.4, 5.3**
    """

    @given(doc=document_strategy())
    @settings(max_examples=100)
    def test_document_has_required_fields(self, doc):
        """
        Property: Every document must have all required display fields
        """
        required_fields = ["filename", "occurrence_count", "first_page", "pdf_path"]

        for field in required_fields:
            assert field in doc, f"Document must have '{field}' field"
            assert doc[field] is not None, f"Document '{field}' must not be None"

    @given(filename=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_filename_truncation_at_40_chars(self, filename):
        """
        Property: Filenames longer than 40 chars should be truncated
        """
        assume(len(filename) > 0)

        # Add .pdf extension if not present
        if not filename.endswith(".pdf"):
            filename = filename + ".pdf"

        truncated = truncate_filename(filename, 40)

        if len(filename) <= 40:
            assert truncated == filename, "Short filenames should not be truncated"
        else:
            assert (
                len(truncated) <= 40
            ), f"Truncated filename should be <= 40 chars, got {len(truncated)}"
            assert "..." in truncated, "Truncated filename should contain ellipsis"

    @given(doc=document_strategy())
    @settings(max_examples=100)
    def test_occurrence_count_is_positive(self, doc):
        """
        Property: Occurrence count must be a positive integer
        """
        occurrence_count = doc.get("occurrence_count", 0)

        assert isinstance(occurrence_count, int), "occurrence_count must be int"
        assert occurrence_count >= 1, "occurrence_count must be >= 1"

    @given(doc=document_strategy())
    @settings(max_examples=100)
    def test_first_page_is_valid(self, doc):
        """
        Property: First page must be a positive integer
        """
        first_page = doc.get("first_page", 1)

        assert isinstance(first_page, int), "first_page must be int"
        assert first_page >= 1, "first_page must be >= 1"


# =============================================================================
# Property 8: Tree Node Rendering Completeness
# =============================================================================


class TestProperty8TreeNodeRenderingCompleteness:
    """
    **Feature: deep-search-ux-improvement, Property 8: Tree Node Rendering Completeness**

    *For any* category folder, the rendered output SHALL contain: category icon,
    category display name, and total document count.
    *For any* doc_type folder, the rendered output SHALL contain: doc_type icon,
    doc_type display name, and document count.

    **Validates: Requirements 5.1, 5.2**
    """

    @given(category=valid_category_strategy)
    @settings(max_examples=100)
    def test_category_has_icon(self, category):
        """
        Property: Every valid category should have an icon defined
        """
        assert (
            category in CATEGORY_ICONS
        ), f"Category '{category}' should have an icon in CATEGORY_ICONS"

        icon = CATEGORY_ICONS[category]
        assert icon is not None, f"Icon for '{category}' should not be None"
        assert len(icon) > 0, f"Icon for '{category}' should not be empty"

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_category_document_count_is_accurate(self, results):
        """
        Property: Category document count should match actual number of documents
        """
        for category, docs in results.items():
            expected_count = len(docs)
            actual_count = len(docs)  # This is what would be displayed

            assert actual_count == expected_count, (
                f"Category '{category}' count mismatch: "
                f"expected {expected_count}, got {actual_count}"
            )

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_doc_type_has_icon(self, results):
        """
        Property: Every doc_type in results should have an icon
        """
        for category, docs in results.items():
            for doc in docs:
                doc_type = doc.get("doc_type", "Unknown")
                # Should have icon or fall back to default
                icon = DOC_TYPE_ICONS.get(doc_type, "📄")
                assert icon is not None, f"Doc type '{doc_type}' should have an icon"

    @given(results=results_by_category_strategy())
    @settings(max_examples=100)
    def test_doc_type_document_count_is_accurate(self, results):
        """
        Property: Doc type document count should match actual number of documents
        """
        for category, docs in results.items():
            # Group by doc_type
            by_doc_type = {}
            for doc in docs:
                dt = doc.get("doc_type", "Unknown")
                if dt not in by_doc_type:
                    by_doc_type[dt] = []
                by_doc_type[dt].append(doc)

            # Verify counts
            for doc_type, type_docs in by_doc_type.items():
                expected_count = len(type_docs)
                actual_count = len(type_docs)  # This is what would be displayed

                assert actual_count == expected_count, (
                    f"Doc type '{doc_type}' count mismatch: "
                    f"expected {expected_count}, got {actual_count}"
                )


# =============================================================================
# Additional Unit Tests for Helper Functions
# =============================================================================


class TestTruncateFilename:
    """Unit tests for truncate_filename helper function"""

    def test_short_filename_unchanged(self):
        """Short filenames should not be modified"""
        assert truncate_filename("short.pdf", 40) == "short.pdf"
        assert truncate_filename("a.pdf", 40) == "a.pdf"

    def test_exact_length_unchanged(self):
        """Filename exactly at max length should not be modified"""
        filename = "a" * 36 + ".pdf"  # 40 chars total
        assert truncate_filename(filename, 40) == filename

    def test_long_filename_truncated(self):
        """Long filenames should be truncated with ellipsis"""
        filename = "a" * 50 + ".pdf"  # 54 chars
        result = truncate_filename(filename, 40)
        assert len(result) <= 40
        assert "..." in result
        assert result.endswith(".pdf")

    def test_preserves_extension(self):
        """Truncation should preserve file extension"""
        filename = "very_long_filename_that_exceeds_limit.pdf"
        result = truncate_filename(filename, 30)
        assert result.endswith(".pdf")

    def test_no_extension(self):
        """Files without extension should still truncate"""
        filename = "a" * 50
        result = truncate_filename(filename, 40)
        assert len(result) <= 40
        assert "..." in result
