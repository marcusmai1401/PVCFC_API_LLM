"""
PDF Viewer Modal Component

Displays PDF pages in a modal overlay with navigation and zoom controls.
Used for viewing citation sources from chat messages and Deep Search results.

Requirements: 2.1, 4.1, 4.2, 4.4, 4.5
"""

from pathlib import Path
from typing import Optional
from urllib.parse import quote

import streamlit as st


def render_pdf_viewer_modal(
    pdf_path: Optional[str] = None,
    page: int = 1,
    title: str = "Document Viewer",
    zoom: float = 1.0,
) -> None:
    """
    Render PDF viewer as an expander at top of page when open.

    Simplified implementation that works reliably with Streamlit.
    """
    # Initialize session state
    if "pdf_modal" not in st.session_state:
        st.session_state.pdf_modal = {"open": False}

    if pdf_path and "pdf_modal" not in st.session_state:
        st.session_state.pdf_modal = {
            "open": True,
            "pdf_path": pdf_path,
            "page": page,
            "title": title,
            "zoom": zoom,
        }

    modal_state = st.session_state.pdf_modal

    # Only render if modal is open
    if not modal_state.get("open", False):
        return

    # Get modal parameters
    current_pdf_path = modal_state.get("pdf_path", "")
    current_page = modal_state.get("page", 1)
    current_title = modal_state.get("title", title)

    # Render PDF viewer as a prominent container at top
    st.markdown("---")

    # Header with close button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader(f"📄 {current_title}")
    with col2:
        if st.button("✖️ Đóng", key="pdf_modal_close", type="primary"):
            st.session_state.pdf_modal["open"] = False
            st.rerun()

    if current_pdf_path:
        pdf_filename = Path(current_pdf_path).name
        encoded_filename = quote(pdf_filename)

        api_base = "http://localhost:8000"
        pdf_url = f"{api_base}/api/search/pdf/{encoded_filename}"

        # Info and link
        st.info(f"**File:** {pdf_filename}")

        # Open in new tab button - this is the most reliable way
        st.markdown(
            f"""
            <a href="{pdf_url}" target="_blank"
               style="display: inline-block; padding: 12px 24px;
                      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      color: white; text-decoration: none; border-radius: 8px;
                      font-weight: 600; font-size: 14px; margin: 8px 0;">
                🔗 Mở PDF trong tab mới (CLICK HERE)
            </a>
            """,
            unsafe_allow_html=True,
        )

        st.caption(f"URL: {pdf_url}")

        st.divider()

        # iframe - maximized for viewing
        st.markdown(
            f"""
            <iframe src="{pdf_url}#page={current_page}"
                    width="100%" height="800px"
                    style="border: none; border-radius: 4px; background-color: #f1f5f9;">
            </iframe>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("⚠️ PDF path không được cung cấp")

    st.markdown("---")


def close_pdf_modal():
    """Close the PDF viewer modal."""
    if "pdf_modal" in st.session_state:
        st.session_state.pdf_modal["open"] = False


def open_pdf_modal(pdf_path: str, page: int = 1, title: str = "Document Viewer"):
    """
    Open PDF viewer modal with specified document.

    Sets the correct session state for pdf_modal integration.

    Args:
        pdf_path: Full path to PDF file
        page: Page number to open (1-indexed)
        title: Document title to display
    """
    st.session_state.pdf_modal = {
        "open": True,
        "pdf_path": pdf_path,
        "page": page,
        "title": title,
        "zoom": 1.0,
    }
