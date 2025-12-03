"""
Deep Search UI Component
========================

Dedicated search interface for keyword-based document discovery.
Unlike RAG search, this returns ALL documents containing the keyword.

Features:
- Keyword search bar
- Category and doc_type filters
- Results grouped by category
- PDF viewer integration with page navigation

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.classification.taxonomy import (
    DocumentTaxonomy,
    get_doc_type_display_name,
    get_taxonomy,
)


# Category icons for visual distinction
CATEGORY_ICONS = {
    "ENGINEERING_DESIGN": "🔧",
    "VENDOR_EQUIPMENT": "📦",
    "OPERATIONS_MAINTENANCE": "⚙️",
    "SAFETY_MANAGEMENT": "🛡️",
    "UNCATEGORIZED": "❓",
}


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
        max_results: int = 1000
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
            params = {
                "keyword": keyword,
                "max_results": max_results
            }
            if category:
                params["category"] = category
            if doc_type:
                params["doc_type"] = doc_type
            
            response = requests.get(
                f"{self.api_base_url}/search/documents",
                params=params,
                timeout=30
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
        # Demo data
        mock_results = [
            {
                "doc_id": "pid_001",
                "filename": "K06101_PID_Sheet1.pdf",
                "category": "ENGINEERING_DESIGN",
                "doc_type": "P&ID",
                "occurrence_count": 5,
                "first_page": 3,
                "snippet": f"...equipment tag {keyword} located in section A-1...",
                "pdf_path": "D:/Data_Raw/K06101/PID/K06101_PID_Sheet1.pdf"
            },
            {
                "doc_id": "pid_002",
                "filename": "K06101_PID_Sheet2.pdf",
                "category": "ENGINEERING_DESIGN",
                "doc_type": "P&ID",
                "occurrence_count": 3,
                "first_page": 1,
                "snippet": f"...reference to {keyword} in process flow...",
                "pdf_path": "D:/Data_Raw/K06101/PID/K06101_PID_Sheet2.pdf"
            },
            {
                "doc_id": "ds_001",
                "filename": "Hitachi_Compressor_Datasheet.pdf",
                "category": "VENDOR_EQUIPMENT",
                "doc_type": "Datasheet",
                "occurrence_count": 12,
                "first_page": 5,
                "snippet": f"...specifications for {keyword} model series...",
                "pdf_path": "D:/Data_Raw/K06101/Vendor/Hitachi_Compressor_Datasheet.pdf"
            },
            {
                "doc_id": "op_001",
                "filename": "K06101_SOP_Startup.pdf",
                "category": "OPERATIONS_MAINTENANCE",
                "doc_type": "Operation Instruction",
                "occurrence_count": 8,
                "first_page": 12,
                "snippet": f"...startup procedure for {keyword} system...",
                "pdf_path": "D:/Data_Raw/K06101/Operations/K06101_SOP_Startup.pdf"
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
            "results_by_category": results_by_category
        }

    def render_search_bar(self) -> tuple:
        """
        Render search bar with filters
        
        Returns:
            Tuple of (keyword, category_filter, doc_type_filter)
        """
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 16px; padding: 24px; margin-bottom: 24px;">
                <h2 style="color: white; margin: 0 0 8px 0; font-size: 24px; font-weight: 600;">
                    🔍 Deep Discovery Search
                </h2>
                <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 14px;">
                    Find ALL documents containing your keyword - no top_k limits
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Search input row
        col_search, col_btn = st.columns([4, 1])
        
        with col_search:
            keyword = st.text_input(
                "Search keyword",
                placeholder="Enter keyword to search across all documents...",
                key="deep_search_keyword",
                label_visibility="collapsed"
            )
        
        with col_btn:
            search_clicked = st.button(
                "🔍 Search",
                key="deep_search_btn",
                type="primary",
                use_container_width=True
            )
        
        # Filter row
        col_cat, col_type = st.columns(2)
        
        with col_cat:
            categories = ["All Categories"] + self.taxonomy.get_all_categories()
            selected_category = st.selectbox(
                "Filter by Category",
                categories,
                key="deep_search_category"
            )
        
        with col_type:
            # Doc types depend on selected category
            if selected_category and selected_category != "All Categories":
                doc_types = ["All Types"] + self.taxonomy.get_doc_types_for_category(selected_category)
            else:
                doc_types = ["All Types"] + self.taxonomy.get_all_doc_types()
            
            selected_doc_type = st.selectbox(
                "Filter by Document Type",
                doc_types,
                key="deep_search_doc_type"
            )
        
        # Process filters
        category_filter = None if selected_category == "All Categories" else selected_category
        doc_type_filter = None if selected_doc_type == "All Types" else selected_doc_type
        
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
            unsafe_allow_html=True
        )
        
        # Action button
        if st.button(
            f"👁️ View Document (Page {first_page})",
            key=f"view_result_{doc_id}_{index}",
            use_container_width=True
        ):
            self._open_pdf_viewer(pdf_path, first_page, filename)

    def _open_pdf_viewer(self, pdf_path: str, page: int, title: str) -> None:
        """
        Open PDF viewer at specified page
        
        Args:
            pdf_path: Path to PDF file
            page: Page number to open
            title: Document title
        """
        if pdf_path and Path(pdf_path).exists():
            # Use the embedded PDF viewer
            st.session_state.pdf_viewer_state = {
                "open": True,
                "pdf_path": pdf_path,
                "page": page,
                "title": title
            }
            st.rerun()
        else:
            st.warning(f"PDF file not found: {pdf_path}")

    def render_category_group(
        self,
        category: str,
        results: List[Dict],
        start_index: int
    ) -> int:
        """
        Render results grouped under a category
        
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
            f"{icon} {display_name} ({len(results)} documents)",
            expanded=True
        ):
            for i, result in enumerate(results):
                self.render_result_card(result, start_index + i)
        
        return start_index + len(results)

    def render_results(self, response: Dict) -> None:
        """
        Render search results
        
        Args:
            response: Search response dict
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
            unsafe_allow_html=True
        )
        
        if total == 0:
            st.info("No documents found matching your search criteria.")
            return
        
        # Render results grouped by category
        index = 0
        for category in self.taxonomy.get_all_categories():
            if category in results_by_category and results_by_category[category]:
                index = self.render_category_group(
                    category,
                    results_by_category[category],
                    index
                )

    def render_empty_state(self) -> None:
        """Render empty state when no search has been performed"""
        st.markdown(
            """
            <div style="text-align: center; padding: 60px 20px; color: #86868b;">
                <div style="font-size: 64px; margin-bottom: 16px;">🔍</div>
                <h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 600; color: #1d1d1f;">
                    Start Your Search
                </h3>
                <p style="margin: 0; font-size: 14px; max-width: 400px; margin: 0 auto;">
                    Enter a keyword above to find all documents containing that term.
                    Unlike RAG search, Deep Search returns every matching document.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Tips section
        st.markdown("---")
        st.markdown("### 💡 Search Tips")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(
                """
                **What is Deep Search?**
                - Finds ALL documents containing your keyword
                - No top_k limits like RAG search
                - Perfect for audits and comprehensive reviews
                """
            )
        
        with col2:
            st.markdown(
                """
                **Best Practices**
                - Use specific equipment tags (e.g., "K-06101")
                - Search for technical terms or part numbers
                - Use filters to narrow results by category
                """
            )

    def render(self) -> None:
        """Main render function for Deep Search UI"""
        # Page header
        st.markdown(
            """
            <div style="margin-bottom: 24px;">
                <h1 style="font-size: 34px; font-weight: 700; margin: 0;">🔍 Deep Search</h1>
                <p style="color: #86868b; margin: 8px 0 0 0;">
                    Comprehensive keyword search across all documents
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Search bar and filters
        keyword, category_filter, doc_type_filter, search_clicked = self.render_search_bar()
        
        st.markdown("---")
        
        # Handle search
        if search_clicked and keyword:
            with st.spinner("Searching documents..."):
                # Try API first
                response = self.search_documents(
                    keyword=keyword,
                    category=category_filter,
                    doc_type=doc_type_filter
                )
                
                if response is None:
                    # Fallback to mock data
                    st.info("📡 API not available. Showing demo results.")
                    response = self.get_mock_results(keyword)
                    
                    # Apply filters to mock data
                    if category_filter:
                        response["results"] = [
                            r for r in response["results"]
                            if r["category"] == category_filter
                        ]
                        response["results_by_category"] = {
                            k: v for k, v in response["results_by_category"].items()
                            if k == category_filter
                        }
                    
                    if doc_type_filter:
                        response["results"] = [
                            r for r in response["results"]
                            if r["doc_type"] == doc_type_filter
                        ]
                        for cat in response["results_by_category"]:
                            response["results_by_category"][cat] = [
                                r for r in response["results_by_category"][cat]
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
