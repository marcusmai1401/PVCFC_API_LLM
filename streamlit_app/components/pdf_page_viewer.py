"""
PDF Page Viewer Component

Extracts and displays specific pages from PDF files.
Uses PyMuPDF (fitz) if available, fallback to full PDF display.
"""

import base64
import io
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st

# Try to import PDF processing libraries
try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def extract_pdf_page_as_image(
    pdf_path: str, page_num: int = 1, zoom: float = 2.0
) -> Optional[bytes]:
    """
    Extract a specific page from PDF as an image.

    Args:
        pdf_path: Path to PDF file
        page_num: Page number (1-indexed)
        zoom: Zoom factor for rendering

    Returns:
        Image bytes in PNG format, or None if extraction fails
    """
    if not PYMUPDF_AVAILABLE:
        return None

    try:
        # Open PDF
        pdf_doc = fitz.open(pdf_path)

        # Check if page number is valid
        if page_num < 1 or page_num > pdf_doc.page_count:
            pdf_doc.close()
            return None

        # Get the page (0-indexed internally)
        page = pdf_doc[page_num - 1]

        # Render page to image with zoom
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")

        # Clean up
        pdf_doc.close()

        return img_data

    except Exception as e:
        st.error(f"Error extracting page: {str(e)}")
        return None


def render_pdf_page(
    pdf_path: str, page_num: int = 1, zoom: float = 1.5, show_controls: bool = True
) -> Tuple[bool, int]:
    """
    Render a specific page from a PDF file.

    Args:
        pdf_path: Path to PDF file
        page_num: Page number to display (1-indexed)
        zoom: Zoom factor
        show_controls: Whether to show navigation controls

    Returns:
        Tuple of (success, total_pages)
    """
    if not Path(pdf_path).exists():
        st.error(f"❌ PDF file not found: {pdf_path}")
        return False, 0

    # Try to extract page as image
    if PYMUPDF_AVAILABLE:
        try:
            # Get total page count
            pdf_doc = fitz.open(pdf_path)
            total_pages = pdf_doc.page_count
            pdf_doc.close()

            # Extract and display page
            img_data = extract_pdf_page_as_image(pdf_path, page_num, zoom)

            if img_data:
                # Display as image
                st.image(
                    img_data,
                    caption=f"Page {page_num} of {total_pages}",
                    use_column_width=True,
                )

                # Show page info
                if show_controls:
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        st.markdown(
                            f"<div style='text-align: center; color: #666;'>"
                            f"📄 Page {page_num} / {total_pages}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                return True, total_pages

        except Exception as e:
            st.warning(f"⚠️ Could not extract page {page_num}: {str(e)}")

    # Fallback: Display full PDF with warning
    st.warning(
        "⚠️ Page-specific display not available. Install PyMuPDF for better PDF viewing:\n"
        "```bash\n"
        "pip install PyMuPDF\n"
        "```"
    )

    # Show full PDF as fallback
    with open(pdf_path, "rb") as pdf_file:
        pdf_bytes = pdf_file.read()

    base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    pdf_display = f"""
        <embed
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="600px"
            type="application/pdf">
        </embed>
        <p style="text-align: center; color: #ff9500; margin-top: 8px;">
            ⚠️ Showing full PDF. Requested page: {page_num}
        </p>
    """

    st.markdown(pdf_display, unsafe_allow_html=True)

    return False, 0


def render_enhanced_pdf_modal():
    """
    Enhanced PDF modal with page extraction support.
    """
    if "pdf_modal" not in st.session_state:
        st.session_state.pdf_modal = {"open": False}

    modal_state = st.session_state.pdf_modal

    if not modal_state.get("open", False):
        return

    pdf_path = modal_state.get("pdf_path", "")
    page_num = modal_state.get("page", 1)
    title = modal_state.get("title", "Document Viewer")
    zoom = modal_state.get("zoom", 1.5)

    # Create modal using Streamlit's dialog-like approach
    # First render backdrop
    st.markdown(
        """
        <style>
        /* Modal backdrop */
        .pvcfc-pdf-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            z-index: 9998;
        }

        /* Modal container */
        .pvcfc-pdf-modal {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: min(95vw, 1100px);
            height: min(90vh, 800px);
            background: white;
            border-radius: 20px;
            box-shadow: 0 25px 70px rgba(0, 0, 0, 0.4);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* Modal header */
        .pvcfc-pdf-header {
            padding: 20px 24px;
            border-bottom: 1px solid #e5e5e5;
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #f8f9fa;
        }

        /* Modal body */
        .pvcfc-pdf-body {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #fafafa;
        }

        /* Force Streamlit container positioning */
        div[data-testid="stVerticalBlock"]:has(.pvcfc-pdf-content) {
            position: fixed !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            width: min(93vw, 1050px) !important;
            height: min(85vh, 750px) !important;
            z-index: 10000 !important;
            background: white !important;
            border-radius: 20px !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
        </style>
        <div class="pvcfc-pdf-backdrop"></div>
        """,
        unsafe_allow_html=True,
    )

    # Modal container with marker class
    with st.container():
        # Add marker class for CSS targeting
        st.markdown('<div class="pvcfc-pdf-content"></div>', unsafe_allow_html=True)

        # Header
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"### 📄 {title}")
        with col2:
            if st.button("✖️ Close", key="pdf_modal_close", type="primary"):
                st.session_state.pdf_modal["open"] = False
                st.rerun()

        # Display PDF page
        if pdf_path:
            success, total_pages = render_pdf_page(
                pdf_path, page_num, zoom, show_controls=False
            )

            # Navigation controls
            if success and total_pages > 0:
                st.markdown("---")
                col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

                with col1:
                    if st.button(
                        "⬅️ Prev", key="pdf_prev_page", disabled=(page_num <= 1)
                    ):
                        st.session_state.pdf_modal["page"] = page_num - 1
                        st.rerun()

                with col2:
                    if st.button(
                        "Next ➡️",
                        key="pdf_next_page",
                        disabled=(page_num >= total_pages),
                    ):
                        st.session_state.pdf_modal["page"] = page_num + 1
                        st.rerun()

                with col3:
                    # Page selector
                    new_page = st.number_input(
                        "Page",
                        min_value=1,
                        max_value=total_pages,
                        value=page_num,
                        key="pdf_page_select",
                    )
                    if new_page != page_num:
                        st.session_state.pdf_modal["page"] = new_page
                        st.rerun()

                with col4:
                    # Zoom controls
                    zoom_options = {
                        "50%": 0.5,
                        "75%": 0.75,
                        "100%": 1.0,
                        "150%": 1.5,
                        "200%": 2.0,
                    }
                    selected_zoom = st.selectbox(
                        "Zoom",
                        options=list(zoom_options.keys()),
                        index=2,  # Default 100%
                        key="pdf_zoom_select",
                    )
                    new_zoom = zoom_options[selected_zoom]
                    if abs(new_zoom - zoom) > 0.01:
                        st.session_state.pdf_modal["zoom"] = new_zoom
                        st.rerun()

                with col5:
                    # Download button
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "📥 Download",
                            data=f.read(),
                            file_name=Path(pdf_path).name,
                            mime="application/pdf",
                        )

        st.markdown("</div>", unsafe_allow_html=True)


def open_pdf_modal(pdf_path: str, page: int = 1, title: str = "Document Viewer"):
    """
    Helper function to open PDF modal with specific page.
    Compatible with pdf_viewer_modal.py interface.

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
        "zoom": 1.5,
    }
