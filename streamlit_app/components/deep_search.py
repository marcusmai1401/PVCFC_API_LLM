"""
Deep Search UI Component
========================

Dedicated search interface for keyword-based document discovery.
Unlike RAG search, this returns ALL documents containing the keyword.

Features:
- Keyword search bar
- Category and doc_type filters
- Results grouped by category with folder tree view
- PDF viewer integration with page navigation

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 5.1, 5.2, 5.3, 5.4, 5.5
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def load_deep_search_css():
    """Load CSS styles for folder tree and PDF modal.

    Requirements: 5.1, 5.2, 5.3
    """
    css_path = Path(__file__).parent.parent / "styles" / "deep_search.css"
    if css_path.exists():
        with open(css_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


from app.classification.taxonomy import (
    DocumentTaxonomy,
    get_doc_type_display_name,
    get_taxonomy,
)

# Category icons for visual distinction
CATEGORY_ICONS = {
    "ENGINEERING_DESIGN": "",
    "VENDOR_EQUIPMENT": "",
    "OPERATIONS_MAINTENANCE": "",
    "SAFETY_MANAGEMENT": "",
    "UNCATEGORIZED": "",
}

# Doc type icons for visual distinction
DOC_TYPE_ICONS = {
    "P&ID": "",
    "Drawing": "",
    "Technical Data": "",
    "Datasheet": "",
    "Material Partlist": "",
    "Vendor Manual": "",
    "Operation Instruction": "",
    "Maintenance Instruction": "",
    "Maintenance History": "",
    "Inventory": "",
    "MOC": "",
    "RCA": "",
    "Pictures": "",
    "Unknown": "",
}


def init_folder_tree_state() -> None:
    """
    Initialize folder tree expansion state in session state.
    Creates folder_tree_state dict if it doesn't exist.

    Requirements: 1.2, 1.3
    """
    if "folder_tree_state" not in st.session_state:
        st.session_state.folder_tree_state = {}


def toggle_folder(folder_key: str) -> None:
    """
    Toggle folder expand/collapse state.

    Args:
        folder_key: Unique key for the folder (e.g., "ENGINEERING_DESIGN" or "ENGINEERING_DESIGN_P&ID")

    Requirements: 1.2, 1.3
    """
    init_folder_tree_state()
    current_state = st.session_state.folder_tree_state.get(folder_key, False)
    st.session_state.folder_tree_state[folder_key] = not current_state


def is_folder_expanded(folder_key: str) -> bool:
    """
    Check if a folder is expanded.

    Args:
        folder_key: Unique key for the folder

    Returns:
        True if folder is expanded, False otherwise
    """
    init_folder_tree_state()
    return st.session_state.folder_tree_state.get(folder_key, False)


def truncate_filename(filename: str, max_length: int = 40) -> str:
    """
    Truncate filename if it exceeds max_length.

    Args:
        filename: Original filename
        max_length: Maximum length before truncation

    Returns:
        Truncated filename with ellipsis if needed

    Requirements: 1.4, 5.3
    """
    if len(filename) <= max_length:
        return filename
    # Keep extension visible
    name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
    if ext:
        available = max_length - len(ext) - 4  # 4 for "..." and "."
        return f"{name[:available]}...{ext}"
    return f"{filename[:max_length-3]}..."


class DeepSearchUI:
    """
    Deep Discovery Search UI Component

    Features:
    - Keyword search with phrase matching
    - Category/doc_type filtering
    - Results grouped by category
    - PDF viewer integration
    """

    def __init__(self, api_base_url: str = "http://localhost:8000/api"):
        """
        Initialize Deep Search UI

        Args:
            api_base_url: Base URL for search API
        """
        self.api_base_url = api_base_url
        self.taxonomy = get_taxonomy()

    def search_documents(
        self,
        keyword: str,
        category: Optional[str] = None,
        doc_type: Optional[str] = None,
        max_results: int = 1000,
    ) -> Optional[Dict]:
        """
        Execute deep search via API

        Args:
            keyword: Search keyword
            category: Optional category filter
            doc_type: Optional doc_type filter
            max_results: Maximum results to return

        Returns:
            Search response dict or None on error
        """
        try:
            params = {"keyword": keyword, "max_results": max_results}
            if category:
                params["category"] = category
            if doc_type:
                params["doc_type"] = doc_type

            response = requests.get(
                f"{self.api_base_url}/search/documents", params=params, timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Search failed: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            st.error(f"Search request failed: {e}")
            return None

    def get_mock_results(self, keyword: str) -> Dict:
        """
        Get mock search results for demo when API is not available

        Args:
            keyword: Search keyword

        Returns:
            Mock search response
        """
        # Get base path from config
        try:
            from app.config.pipeline_config import get_config

            base_path = str(get_config().DOCUMENTS_DIR)
        except Exception:
            base_path = "D:/Data_Raw"

        # Demo data with dynamic paths
        mock_results = [
            {
                "doc_id": "pid_001",
                "filename": "K06101_PID_Sheet1.pdf",
                "category": "ENGINEERING_DESIGN",
                "doc_type": "P&ID",
                "occurrence_count": 5,
                "first_page": 3,
                "snippet": f"...equipment tag {keyword} located in section A-1...",
                "pdf_path": f"{base_path}/K06101/PID/K06101_PID_Sheet1.pdf",
            },
            {
                "doc_id": "pid_002",
                "filename": "K06101_PID_Sheet2.pdf",
                "category": "ENGINEERING_DESIGN",
                "doc_type": "P&ID",
                "occurrence_count": 3,
                "first_page": 1,
                "snippet": f"...reference to {keyword} in process flow...",
                "pdf_path": f"{base_path}/K06101/PID/K06101_PID_Sheet2.pdf",
            },
            {
                "doc_id": "ds_001",
                "filename": "Hitachi_Compressor_Datasheet.pdf",
                "category": "VENDOR_EQUIPMENT",
                "doc_type": "Datasheet",
                "occurrence_count": 12,
                "first_page": 5,
                "snippet": f"...specifications for {keyword} model series...",
                "pdf_path": f"{base_path}/K06101/Vendor/Hitachi_Compressor_Datasheet.pdf",
            },
            {
                "doc_id": "op_001",
                "filename": "K06101_SOP_Startup.pdf",
                "category": "OPERATIONS_MAINTENANCE",
                "doc_type": "Operation Instruction",
                "occurrence_count": 8,
                "first_page": 12,
                "snippet": f"...startup procedure for {keyword} system...",
                "pdf_path": f"{base_path}/K06101/Operations/K06101_SOP_Startup.pdf",
            },
        ]

        # Group by category
        results_by_category = {}
        for result in mock_results:
            cat = result["category"]
            if cat not in results_by_category:
                results_by_category[cat] = []
            results_by_category[cat].append(result)

        return {
            "query": keyword,
            "total_documents": len(mock_results),
            "results": mock_results,
            "results_by_category": results_by_category,
        }

    def render_search_bar(self) -> tuple:
        """
        Render search bar with filters

        Returns:
            Tuple of (keyword, category_filter, doc_type_filter)
        """

        # Search input row
        col_search, col_btn = st.columns([4, 1])

        with col_search:
            keyword = st.text_input(
                "Search keyword",
                placeholder="Enter keyword to search across all documents...",
                key="deep_search_keyword",
                label_visibility="collapsed",
            )

        with col_btn:
            search_clicked = st.button(
                "🔍 Search",
                key="deep_search_btn",
                type="primary",
                use_container_width=True,
            )

        # Filter row
        col_cat, col_type = st.columns(2)

        with col_cat:
            categories = ["All Categories"] + self.taxonomy.get_all_categories()
            selected_category = st.selectbox(
                "Filter by Category", categories, key="deep_search_category"
            )

        with col_type:
            # Doc types depend on selected category
            if selected_category and selected_category != "All Categories":
                doc_types = ["All Types"] + self.taxonomy.get_doc_types_for_category(
                    selected_category
                )
            else:
                doc_types = ["All Types"] + self.taxonomy.get_all_doc_types()

            selected_doc_type = st.selectbox(
                "Filter by Document Type", doc_types, key="deep_search_doc_type"
            )

        # Process filters
        category_filter = (
            None if selected_category == "All Categories" else selected_category
        )
        doc_type_filter = (
            None if selected_doc_type == "All Types" else selected_doc_type
        )

        return keyword, category_filter, doc_type_filter, search_clicked

    def render_result_card(self, result: Dict, index: int) -> None:
        """
        Render single search result card

        Args:
            result: Search result dict
            index: Result index for unique keys
        """
        doc_id = result.get("doc_id", "")
        filename = result.get("filename", "Unknown")
        doc_type = result.get("doc_type", "Unknown")
        occurrence_count = result.get("occurrence_count", 0)
        first_page = result.get("first_page", 1)
        snippet = result.get("snippet", "")
        pdf_path = result.get("pdf_path", "")

        # Card container
        st.markdown(
            f"""
            <div style="background: #f5f5f7; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="flex: 1;">
                        <h4 style="margin: 0 0 4px 0; font-size: 16px; font-weight: 600; color: #1d1d1f;">
                            📄 {filename}
                        </h4>
                        <p style="margin: 0 0 8px 0; font-size: 13px; color: #86868b;">
                            {get_doc_type_display_name(doc_type)} • {occurrence_count} occurrences • First on page {first_page}
                        </p>
                    </div>
                </div>
                {f'<p style="margin: 8px 0 0 0; font-size: 14px; color: #424245; background: #fff; padding: 8px 12px; border-radius: 8px; border-left: 3px solid #667eea;">{snippet}</p>' if snippet else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Action button
        if st.button(
            f"👁️ View Document (Page {first_page})",
            key=f"view_result_{doc_id}_{index}",
            use_container_width=True,
        ):
            self._open_pdf_viewer(pdf_path, first_page, filename)

    def _open_pdf_viewer(self, pdf_path: str, page: int, title: str) -> None:
        """
        Open PDF viewer modal at specified page.

        Uses the correct session state key `pdf_modal` for integration with
        pdf_viewer_modal.py component.

        Args:
            pdf_path: Path to PDF file
            page: Page number to open (1-indexed)
            title: Document title

        Requirements: 2.1, 2.3
        """
        # Validate pdf_path is provided
        if not pdf_path:
            st.error("PDF file path is invalid: No path provided")
            return

        # NOTE: File existence check removed - PDF is served via API endpoint
        # which searches recursively in DOCUMENTS_DIR

        # Use correct session state key `pdf_modal` (not `pdf_viewer_state`)
        # This integrates with pdf_viewer_modal.py component
        st.session_state.pdf_modal = {
            "open": True,
            "pdf_path": pdf_path,
            "page": page,
            "title": title,
            "zoom": 1.0,
        }
        st.rerun()

    def render_category_group(
        self, category: str, results: List[Dict], start_index: int
    ) -> int:
        """
        Render results grouped under a category (legacy method)

        Args:
            category: Category name
            results: List of results in this category
            start_index: Starting index for unique keys

        Returns:
            Next available index
        """
        icon = CATEGORY_ICONS.get(category, "📁")
        display_name = self.taxonomy.get_display_name(category)

        with st.expander(
            f"{icon} {display_name} ({len(results)} documents)", expanded=True
        ):
            for i, result in enumerate(results):
                self.render_result_card(result, start_index + i)

        return start_index + len(results)

    def render_folder_tree(self, results_by_category: Dict) -> None:
        """
        Render results as collapsible folder tree.
        Categories are root level, doc_types are children, documents are leaves.

        Args:
            results_by_category: Dict mapping category to list of results

        Requirements: 1.1, 1.5, 5.1
        """
        init_folder_tree_state()

        # Load CSS styles for folder tree
        load_deep_search_css()

        # Add custom CSS for left-aligned buttons in the tree
        st.markdown(
            """
            <style>
            /* Force left alignment for tertiary buttons in the tree */
            div[data-testid="stVerticalBlock"] button[kind="tertiary"] div[data-testid="stMarkdownContainer"] p {
                text-align: left !important;
                padding-left: 0 !important;
            }
            div[data-testid="stVerticalBlock"] button[kind="tertiary"] {
                justify-content: flex-start !important;
                padding-left: 0 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Get all categories in order
        all_categories = self.taxonomy.get_all_categories()

        # Filter out empty categories (Requirement 1.5)
        non_empty_categories = [
            cat
            for cat in all_categories
            if cat in results_by_category and len(results_by_category[cat]) > 0
        ]

        if not non_empty_categories:
            st.info("No documents found matching your search criteria.")
            return

        # Folder tree container with CSS styling
        st.markdown('<div class="folder-tree-container">', unsafe_allow_html=True)

        # Render each category as a root folder
        for category in non_empty_categories:
            results = results_by_category[category]
            self.render_category_folder(category, results)

        st.markdown("</div>", unsafe_allow_html=True)

    def render_category_folder(self, category: str, results: List[Dict]) -> None:
        """
        Render category level folder with expand/collapse.
        Uses clickable header with large arrow indicator for professional UX.

        Args:
            category: Category name
            results: List of results in this category

        Requirements: 5.1, 5.4, 5.5
        """
        folder_key = category
        is_expanded = is_folder_expanded(folder_key)

        # Get category info
        icon = CATEGORY_ICONS.get(category, "📁")
        display_name = self.taxonomy.get_display_name(category)
        doc_count = len(results)

        # Arrow indicator (▼ for expanded, ▶ for collapsed) - large and clear
        arrow = "▼" if is_expanded else "▶"

        # Create clickable header using columns for better control
        col_arrow, col_name, col_count = st.columns([0.5, 8, 1.5])

        with col_arrow:
            # Toggle button
            if st.button(
                arrow,
                key=f"cat_toggle_{category}",
                help="Expand/Collapse",
                type="tertiary",
            ):
                toggle_folder(folder_key)
                st.rerun()

        with col_name:
            # Bold Category Name using Markdown (UPPERCASE)
            st.markdown(f"##### **{display_name.upper()}**", unsafe_allow_html=True)

        with col_count:
            st.markdown(
                f"<div style='text-align: right; color: #64748b; padding-top: 5px;'>{doc_count} documents</div>",
                unsafe_allow_html=True,
            )

        # Render children if expanded
        if is_expanded:
            # Group results by doc_type
            results_by_doc_type = {}
            for result in results:
                doc_type = result.get("doc_type", "Unknown")
                if doc_type not in results_by_doc_type:
                    results_by_doc_type[doc_type] = []
                results_by_doc_type[doc_type].append(result)

            # Indented container for children with continuous vertical line
            # This creates the main vertical line of the tree
            st.markdown(
                '<div style="margin-left: 28px; border-left: 2px solid #cbd5e1; padding-left: 0;">',
                unsafe_allow_html=True,
            )

            # Render each doc_type folder
            for doc_type, docs in results_by_doc_type.items():
                self.render_doc_type_folder(category, doc_type, docs)

            st.markdown("</div>", unsafe_allow_html=True)

    def render_doc_type_folder(
        self, category: str, doc_type: str, documents: List[Dict]
    ) -> None:
        """
        Render doc_type level folder with indentation.

        Args:
            category: Parent category name
            doc_type: Document type name
            documents: List of documents of this type

        Requirements: 5.2, 5.4, 5.5
        """
        folder_key = f"{category}_{doc_type}"
        is_expanded = is_folder_expanded(folder_key)

        # Get doc_type info
        display_name = get_doc_type_display_name(doc_type)
        doc_count = len(documents)

        # Arrow indicator
        arrow = "▼" if is_expanded else "▶"

        # Custom layout for Doc Type Header (Tree Style - Clean)
        # Removed horizontal connector, just indentation
        col_indent, col_arrow, col_name, col_count = st.columns([0.2, 0.5, 9.8, 1.5])

        with col_arrow:
            if st.button(
                arrow,
                key=f"dt_toggle_{folder_key}",
                help="Expand/Collapse",
                type="tertiary",
            ):
                toggle_folder(folder_key)
                st.rerun()

        with col_name:
            # Normal weight for Doc Type
            st.markdown(
                f"<div style='padding-top: 5px; font-weight: 500;'>{display_name}</div>",
                unsafe_allow_html=True,
            )

        with col_count:
            st.markdown(
                f"<div style='text-align: right; color: #94a3b8; font-size: 0.9em; padding-top: 5px;'>({doc_count})</div>",
                unsafe_allow_html=True,
            )

        # Render documents if expanded
        if is_expanded:
            # Deeper indent for documents with its own vertical line if needed
            # But for leaf nodes, we just need the connector
            st.markdown(
                '<div style="margin-left: 28px; border-left: 2px solid #cbd5e1; padding-left: 0;">',
                unsafe_allow_html=True,
            )
            for i, doc in enumerate(documents):
                self.render_document_item(doc, f"{folder_key}_{i}")
            st.markdown("</div>", unsafe_allow_html=True)

    def render_document_item(self, doc: Dict, unique_key: str) -> None:
        """
        Render single document item as a clickable button.

        Args:
            doc: Document dict with filename, occurrence_count, first_page, pdf_path
            unique_key: Unique key for button

        Requirements: 1.4, 5.3
        """
        filename = doc.get("filename", "Unknown")
        occurrence_count = doc.get("occurrence_count", 0)
        first_page = doc.get("first_page", 1)
        pdf_path = doc.get("pdf_path", "")

        # Full filename, no truncation
        display_filename = filename

        # Create a descriptive label for the button - Simple text style (No emoji)
        button_label = display_filename

        # Render as a text link button (Tree Style - Clean)
        # Indentation increased to be visually nested under the parent folder
        # Parent text starts at offset ~0.7, so we start at 1.2
        col_indent, col_btn = st.columns([1.2, 10.8])

        with col_btn:
            if st.button(
                button_label,
                key=f"view_{unique_key}",
                help=f"View {filename} • {occurrence_count} occurrences • Page {first_page}",
                use_container_width=True,
                type="tertiary",
            ):
                self._open_pdf_viewer(pdf_path, first_page, filename)

    def render_results(self, response: Dict) -> None:
        """
        Render search results using folder tree view.

        Args:
            response: Search response dict

        Requirements: 1.1, 1.5
        """
        total = response.get("total_documents", 0)
        query = response.get("query", "")
        results_by_category = response.get("results_by_category", {})

        # Results header
        st.markdown(
            f"""
            <div style="margin: 24px 0 16px 0;">
                <h3 style="margin: 0; font-size: 20px; font-weight: 600;">
                    📊 Search Results
                </h3>
                <p style="margin: 4px 0 0 0; color: #86868b; font-size: 14px;">
                    Found <strong>{total}</strong> documents containing "<strong>{query}</strong>"
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if total == 0:
            st.info("No documents found matching your search criteria.")
            return

        # Render results using folder tree view (Requirements: 1.1, 1.5)
        self.render_folder_tree(results_by_category)

    def render_empty_state(self) -> None:
        """Render empty state when no search has been performed"""
        st.markdown(
            """
            <div style="text-align: center; padding: 60px 20px; color: #86868b;">
            </div>
            """,
            unsafe_allow_html=True,
        )

    def render(self) -> None:
        """Main render function for Deep Search UI"""
        # Page header
        st.markdown(
            """
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                <div>
                    <h2 style="margin: 0;">Deep Search</h2>
                    <p style="margin: 4px 0 0 0; color: var(--color-text-secondary);">Comprehensive keyword search across all documents</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Search bar and filters
        (
            keyword,
            category_filter,
            doc_type_filter,
            search_clicked,
        ) = self.render_search_bar()

        st.markdown("---")

        # Handle search
        if search_clicked and keyword:
            with st.spinner("Searching documents..."):
                # Try API first
                response = self.search_documents(
                    keyword=keyword, category=category_filter, doc_type=doc_type_filter
                )

                if response is None:
                    # Fallback to mock data
                    st.info("📡 API not available. Showing demo results.")
                    response = self.get_mock_results(keyword)

                    # Apply filters to mock data
                    if category_filter:
                        response["results"] = [
                            r
                            for r in response["results"]
                            if r["category"] == category_filter
                        ]
                        response["results_by_category"] = {
                            k: v
                            for k, v in response["results_by_category"].items()
                            if k == category_filter
                        }

                    if doc_type_filter:
                        response["results"] = [
                            r
                            for r in response["results"]
                            if r["doc_type"] == doc_type_filter
                        ]
                        for cat in response["results_by_category"]:
                            response["results_by_category"][cat] = [
                                r
                                for r in response["results_by_category"][cat]
                                if r["doc_type"] == doc_type_filter
                            ]

                    response["total_documents"] = len(response["results"])

                # Store results in session state
                st.session_state["deep_search_results"] = response

        # Display results or empty state
        if "deep_search_results" in st.session_state:
            self.render_results(st.session_state["deep_search_results"])
        elif keyword and not search_clicked:
            # User typed but didn't click search yet
            st.info("Press Enter or click Search to find documents.")
        else:
            self.render_empty_state()


def render():
    """Main render function for deep search component"""
    search_ui = DeepSearchUI()
    search_ui.render()
