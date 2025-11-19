"""
Modern Document Browser Component
Browse and filter documents with a clean grid view.
"""

import json
import os
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

# Try to import classification utilities
try:
    from app.classification.document_type_12 import get_doc_type_display_name
except ImportError:
    # Fallback mock
    def get_doc_type_display_name(code):
        return code.replace("_", " ").title()


# Import Split View Controller
try:
    from streamlit_app.components.split_layout import open_pdf_panel
except ImportError:
    from components.split_layout import open_pdf_panel


class DocumentBrowser:
    def __init__(self):
        self.manifest_path = Path("artifacts/classification/document_types_12.jsonl")
        self._docs = None

    def load_documents(self) -> List[Dict]:
        """Load documents from manifest."""
        if self._docs is not None:
            return self._docs

        docs = []
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            docs.append(json.loads(line))
                        except:
                            pass
        self._docs = docs
        return docs

    def get_unique_equipment(self) -> List[str]:
        """Extract unique equipment IDs."""
        docs = self.load_documents()
        eq_ids = set()
        for doc in docs:
            path = doc.get("pdf_path", "")
            # Simple extraction heuristic based on known patterns
            # Adjust based on your actual data pattern
            parts = Path(path).parts
            for part in parts:
                if "K06101" in part or "KT06101" in part:  # Example patterns
                    eq_ids.add(part.split("_")[0])  # Take first part of folder name

        # Fallback: if extraction fails, use top-level folders
        if not eq_ids:
            return ["All Equipment"]

        return sorted(list(eq_ids))


def render_doc_browser():
    """Main render function."""
    browser = DocumentBrowser()
    docs = browser.load_documents()

    # 1. Header
    st.markdown(
        """
        <div style="margin-bottom: 1.5rem;">
            <h2>Document Explorer</h2>
            <p class="text-muted">Browse {count} indexed documents across the facility.</p>
        </div>
        """.format(
            count=len(docs)
        ),
        unsafe_allow_html=True,
    )

    # 2. Filters (Sidebar-like top section)
    with st.container():
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 2, 3])

        with col1:
            # Filter by Type
            doc_types = sorted(list(set(d.get("doc_type_12", "Unknown") for d in docs)))
            selected_type = st.selectbox("Document Type", ["All Types"] + doc_types)

        with col2:
            # Filter by Equipment (Simplified)
            # Just search by text for now to be robust
            search_term = st.text_input("Search Filename", placeholder="e.g. P-101...")

        st.markdown("</div>", unsafe_allow_html=True)

    # 3. Filter Logic
    filtered_docs = docs
    if selected_type != "All Types":
        filtered_docs = [
            d for d in filtered_docs if d.get("doc_type_12") == selected_type
        ]

    if search_term:
        term = search_term.lower()
        filtered_docs = [
            d for d in filtered_docs if term in d.get("pdf_path", "").lower()
        ]

    # 4. Grid View
    if not filtered_docs:
        st.info("No documents found matching criteria.")
        return

    # Pagination
    ITEMS_PER_PAGE = 12
    if "doc_page" not in st.session_state:
        st.session_state.doc_page = 0

    total_pages = (len(filtered_docs) - 1) // ITEMS_PER_PAGE + 1
    current_page = st.session_state.doc_page

    start_idx = current_page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(filtered_docs))
    page_docs = filtered_docs[start_idx:end_idx]

    # Render Grid
    cols = st.columns(3)
    for i, doc in enumerate(page_docs):
        with cols[i % 3]:
            render_doc_card(doc)

    # Pagination Controls
    st.markdown("<div class='mt-4 flex-center'>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("← Previous", disabled=current_page == 0):
            st.session_state.doc_page -= 1
            st.rerun()
    with c2:
        st.markdown(
            f"<div style='text-align: center; padding-top: 8px;'>Page {current_page + 1} of {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with c3:
        if st.button("Next →", disabled=current_page >= total_pages - 1):
            st.session_state.doc_page += 1
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_doc_card(doc):
    """Render a single document card."""
    filename = Path(doc.get("pdf_path", "")).name
    doc_type = doc.get("doc_type_12", "Unknown")

    # Icon based on type
    icon = "📄"
    if "P_ID" in doc_type:
        icon = "🗺️"
    elif "MANUAL" in doc_type:
        icon = "📘"
    elif "DATASHEET" in doc_type:
        icon = "📋"

    st.markdown(
        f"""
        <div class="card" style="height: 100%; padding: 1rem;">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
            <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 0.25rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{filename}">
                {filename}
            </div>
            <div class="text-muted text-sm" style="margin-bottom: 0.5rem;">
                {doc_type.replace('_', ' ')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # View Button - Opens in Split Panel
    if st.button(
        "Open", key=f"btn_open_{doc.get('doc_id')}_{filename}", use_container_width=True
    ):
        open_pdf_panel(doc.get("pdf_path", ""), 1, doc.get("doc_id", ""))
        st.rerun()
