"""
PDF Viewer Modal Component

Displays PDF pages in a modal overlay with navigation and zoom controls.
Used for viewing citation sources from chat messages.
"""

import base64
from pathlib import Path
from typing import Optional

import streamlit as st


def render_pdf_viewer_modal(
    pdf_path: Optional[str] = None,
    page: int = 1,
    title: str = "Document Viewer",
) -> None:
    """
    Render PDF viewer modal if session state indicates it should be open.

    Args:
        pdf_path: Path to PDF file (overrides session state if provided)
        page: Page number to display (1-indexed)
        title: Modal title
    """
    # Check session state for modal open flag
    if "pdf_modal" not in st.session_state:
        st.session_state.pdf_modal = {"open": False}

    # If explicitly passed, update session state
    if pdf_path:
        st.session_state.pdf_modal = {
            "open": True,
            "pdf_path": pdf_path,
            "page": page,
            "title": title,
            "zoom": 1.0,
        }

    modal_state = st.session_state.pdf_modal

    # Only render if modal is open
    if not modal_state.get("open", False):
        return

    # Get modal parameters
    current_pdf_path = modal_state.get("pdf_path", "")
    current_page = modal_state.get("page", 1)
    current_title = modal_state.get("title", title)
    current_zoom = modal_state.get("zoom", 1.0)

    # ISSUE 5 FIX: Render modal with Streamlit buttons/controls (mixed approach)
    # Backdrop
    st.markdown(
        """
        <div class="pvcfc-modal-backdrop" id="pdf-modal-backdrop"
             style="position: fixed; inset: 0; background: rgba(0,0,0,0.6);
                    backdrop-filter: blur(4px); z-index: 9998;"></div>
        """,
        unsafe_allow_html=True,
    )

    # Modal container with fixed positioning
    st.markdown(
        f"""
        <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                    max-width: 90vw; max-height: 90vh; width: 900px;
                    background: white; border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3); z-index: 9999;
                    padding: 24px; overflow: hidden;">
            <h3 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 600;">{current_title}</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Use a container positioned with CSS to align with modal
    modal_content = st.container()

    with modal_content:
        # Add inline style to position this container
        st.markdown(
            """
            <style>
            div[data-testid="stVerticalBlock"] > div:has(button[data-testid="baseButton-primary"]) {
                position: fixed !important;
                top: 52% !important;
                left: 50% !important;
                transform: translate(-50%, -50%) !important;
                width: 850px !important;
                max-width: 85vw !important;
                z-index: 10000 !important;
                background: transparent !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Toolbar
        col1, col2, col3, col4 = st.columns([1, 1, 2, 1])

        with col1:
            if st.button("⬅️ Prev", key="pdf_prev", use_container_width=True):
                if current_page > 1:
                    st.session_state.pdf_modal["page"] = current_page - 1
                    st.rerun()

        with col2:
            if st.button("Next ➡️", key="pdf_next", use_container_width=True):
                st.session_state.pdf_modal["page"] = current_page + 1
                st.rerun()

        with col3:
            st.markdown(
                f'<div style="text-align: center; padding: 12px; font-size: 15px;">Page {current_page}</div>',
                unsafe_allow_html=True,
            )

        with col4:
            if st.button(
                "✖️ Close", key="pdf_close", type="primary", use_container_width=True
            ):
                st.session_state.pdf_modal["open"] = False
                st.rerun()

        st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)

        # PDF Display - Using different approach for page navigation
        if current_pdf_path and Path(current_pdf_path).exists():
            try:
                # Note about pages display
                st.info(f"📄 Showing: {current_title} - Page {current_page}")
                st.caption(
                    "Note: Full PDF viewer with page navigation requires serving PDF files via HTTP. Current implementation shows full PDF."
                )

                # Option 1: Use Streamlit's native file display (shows full PDF, not specific page)
                with open(current_pdf_path, "rb") as pdf_file:
                    pdf_bytes = pdf_file.read()

                # Create download button for better UX
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_bytes,
                        file_name=Path(current_pdf_path).name,
                        mime="application/pdf",
                        use_container_width=True,
                    )

                # Display PDF using base64 (shows full document)
                base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

                # Note: #page parameter doesn't work with data: URIs in most browsers
                # Alternative: Use PDF.js library or serve files via HTTP endpoint
                pdf_display = f"""
                    <embed
                        src="data:application/pdf;base64,{base64_pdf}"
                        width="100%"
                        height="500px"
                        type="application/pdf"
                        style="border: 1px solid #ddd; border-radius: 8px;">
                    </embed>
                    <p style="text-align: center; color: #666; margin-top: 8px; font-size: 14px;">
                        ⚠️ Browser PDF viewer shows full document. Use Prev/Next buttons to navigate to page {current_page}.
                    </p>
                """

                st.markdown(pdf_display, unsafe_allow_html=True)

            except FileNotFoundError:
                st.error(f"❌ PDF file not found: {current_pdf_path}")
            except Exception as e:
                st.error(f"❌ Error loading PDF: {str(e)}")
                # Fallback: show file path for debugging
                st.code(f"File path: {current_pdf_path}\nError: {str(e)}")
        else:
            st.warning("⚠️ PDF file not found or path not specified")
            st.info(f"Path: {current_pdf_path}")
            # Check if file really exists
            if current_pdf_path:
                st.code(f"File exists: {Path(current_pdf_path).exists()}")


def close_pdf_modal():
    """Helper function to close the PDF modal."""
    if "pdf_modal" in st.session_state:
        st.session_state.pdf_modal["open"] = False


def open_pdf_modal(pdf_path: str, page: int = 1, title: str = "Document Viewer"):
    """
    Helper function to open PDF modal.

    Args:
        pdf_path: Path to PDF file
        page: Page number to display (1-indexed)
        title: Modal title
    """
    st.session_state.pdf_modal = {
        "open": True,
        "pdf_path": pdf_path,
        "page": page,
        "title": title,
        "zoom": 1.0,
    }
