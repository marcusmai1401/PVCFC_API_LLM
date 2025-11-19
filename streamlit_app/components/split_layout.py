"""
Split Screen Layout Manager
Manages the side-by-side view of Main Content (Chat/Docs) and PDF Viewer.
"""

from typing import Callable

import streamlit as st


def render_split_view(main_content_func: Callable, pdf_viewer_func: Callable):
    """
    Renders a split-screen layout if a PDF is open, otherwise renders full width.

    Args:
        main_content_func: Function to render the left side (Chat/Browser)
        pdf_viewer_func: Function to render the right side (PDF Viewer)
    """

    # Check if PDF viewer is active
    pdf_state = st.session_state.get("pdf_viewer_state", {"open": False})
    is_pdf_open = pdf_state.get("open", False)

    if is_pdf_open:
        # Create 2 columns: Main Content (55%) | PDF Viewer (45%)
        col_main, col_pdf = st.columns([5.5, 4.5], gap="medium")

        with col_main:
            main_content_func()

        with col_pdf:
            # Add a container with border/styling for the PDF panel
            with st.container():
                st.markdown(
                    '<div style="height: 100%; border-left: 1px solid var(--color-border); padding-left: 1rem;">',
                    unsafe_allow_html=True,
                )
                pdf_viewer_func()
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        # Full width render
        main_content_func()


def close_pdf_panel():
    """Close the PDF panel."""
    st.session_state.pdf_viewer_state = {"open": False}
    st.rerun()


def open_pdf_panel(pdf_path: str, page: int = 1, doc_id: str = "Document"):
    """Open the PDF panel."""
    st.session_state.pdf_viewer_state = {
        "open": True,
        "pdf_path": pdf_path,
        "page": page,
        "doc_id": doc_id,
        "zoom": 1.5,
    }
    # Optional: don't rerun immediately to let the calling function finish
