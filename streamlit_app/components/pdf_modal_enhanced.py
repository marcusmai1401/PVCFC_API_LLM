"""
Enhanced PDF Modal Component with Unified Container
Provides a better modal experience with PDF.js integration
"""

import base64
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components


def create_pdf_modal_html(
    pdf_base64: str,
    page: int = 1,
    title: str = "Document Viewer",
    modal_id: str = "pdf-modal",
) -> str:
    """
    Create complete HTML for PDF modal with embedded PDF viewer.

    Args:
        pdf_base64: Base64 encoded PDF data
        page: Initial page number to display
        title: Modal title
        modal_id: Unique ID for modal

    Returns:
        Complete HTML string for modal
    """
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                overflow: hidden;
            }}

            /* Modal backdrop */
            .modal-backdrop {{
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                z-index: 9998;
                animation: fadeIn 0.3s ease;
            }}

            /* Modal container */
            .modal-container {{
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: min(95vw, 1100px);
                height: min(90vh, 800px);
                background: white;
                border-radius: 16px;
                box-shadow: 0 25px 60px rgba(0, 0, 0, 0.4);
                z-index: 9999;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                animation: slideIn 0.3s ease;
            }}

            /* Modal header */
            .modal-header {{
                padding: 16px 24px;
                border-bottom: 1px solid #e5e7eb;
                background: linear-gradient(to bottom, #ffffff, #f9fafb);
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-shrink: 0;
            }}

            .modal-title {{
                font-size: 1.25rem;
                font-weight: 600;
                color: #1f2937;
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .close-button {{
                background: transparent;
                border: none;
                font-size: 1.5rem;
                color: #6b7280;
                cursor: pointer;
                padding: 4px 8px;
                border-radius: 6px;
                transition: all 0.2s;
                line-height: 1;
            }}

            .close-button:hover {{
                background: #f3f4f6;
                color: #374151;
            }}

            /* Modal body */
            .modal-body {{
                flex: 1;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                background: #fafafa;
            }}

            /* PDF viewer container */
            .pdf-container {{
                flex: 1;
                overflow: auto;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                background: #f3f4f6;
            }}

            /* PDF iframe */
            .pdf-viewer {{
                width: 100%;
                height: 100%;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background: white;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}

            /* Toolbar */
            .pdf-toolbar {{
                padding: 12px 24px;
                border-top: 1px solid #e5e7eb;
                background: white;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 16px;
                flex-shrink: 0;
            }}

            .toolbar-button {{
                padding: 6px 12px;
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                gap: 4px;
            }}

            .toolbar-button:hover {{
                background: #2563eb;
                transform: translateY(-1px);
            }}

            .toolbar-button:disabled {{
                background: #9ca3af;
                cursor: not-allowed;
                transform: none;
            }}

            .page-info {{
                font-size: 0.875rem;
                color: #4b5563;
                font-weight: 500;
                padding: 0 12px;
            }}

            .zoom-select {{
                padding: 6px 8px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                color: #374151;
                font-size: 0.875rem;
                cursor: pointer;
            }}

            /* Animations */
            @keyframes fadeIn {{
                from {{ opacity: 0; }}
                to {{ opacity: 1; }}
            }}

            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translate(-50%, -48%) scale(0.96);
                }}
                to {{
                    opacity: 1;
                    transform: translate(-50%, -50%) scale(1);
                }}
            }}

            /* Responsive adjustments */
            @media (max-width: 768px) {{
                .modal-container {{
                    width: 100vw;
                    height: 100vh;
                    border-radius: 0;
                }}

                .pdf-toolbar {{
                    flex-wrap: wrap;
                    gap: 8px;
                }}
            }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    </head>
    <body>
        <div class="modal-backdrop" onclick="closeModal()"></div>

        <div class="modal-container">
            <div class="modal-header">
                <div class="modal-title">
                    <span>📄</span>
                    <span>{title}</span>
                </div>
                <button class="close-button" onclick="closeModal()" title="Close">✕</button>
            </div>

            <div class="modal-body">
                <div class="pdf-container">
                    <iframe
                        id="pdf-viewer"
                        class="pdf-viewer"
                        src="data:application/pdf;base64,{pdf_base64}#page={page}"
                        type="application/pdf"
                    >
                        <p>Your browser does not support PDFs. Please download the PDF to view it.</p>
                    </iframe>
                </div>

                <div class="pdf-toolbar">
                    <button class="toolbar-button" onclick="previousPage()" id="prev-btn">
                        <span>←</span> Previous
                    </button>

                    <span class="page-info" id="page-info">
                        Page <span id="current-page">{page}</span> of <span id="total-pages">-</span>
                    </span>

                    <button class="toolbar-button" onclick="nextPage()" id="next-btn">
                        Next <span>→</span>
                    </button>

                    <select class="zoom-select" onchange="changeZoom(this.value)">
                        <option value="0.5">50%</option>
                        <option value="0.75">75%</option>
                        <option value="1" selected>100%</option>
                        <option value="1.5">150%</option>
                        <option value="2">200%</option>
                    </select>

                    <button class="toolbar-button" onclick="downloadPDF()">
                        <span>📥</span> Download
                    </button>
                </div>
            </div>
        </div>

        <script>
            let currentPage = {page};
            let totalPages = 1;
            let pdfData = "data:application/pdf;base64,{pdf_base64}";

            // Initialize PDF.js if available
            if (typeof pdfjsLib !== 'undefined') {{
                pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

                // Load PDF to get page count
                pdfjsLib.getDocument(pdfData).promise.then(function(pdf) {{
                    totalPages = pdf.numPages;
                    document.getElementById('total-pages').textContent = totalPages;
                    updateButtons();
                }});
            }}

            function closeModal() {{
                // Send message to parent Streamlit app
                window.parent.postMessage({{type: 'close-modal', modalId: '{modal_id}'}}, '*');
            }}

            function updatePage() {{
                const iframe = document.getElementById('pdf-viewer');
                iframe.src = pdfData + '#page=' + currentPage;
                document.getElementById('current-page').textContent = currentPage;
                updateButtons();
            }}

            function updateButtons() {{
                document.getElementById('prev-btn').disabled = currentPage <= 1;
                document.getElementById('next-btn').disabled = currentPage >= totalPages;
            }}

            function previousPage() {{
                if (currentPage > 1) {{
                    currentPage--;
                    updatePage();
                }}
            }}

            function nextPage() {{
                if (currentPage < totalPages) {{
                    currentPage++;
                    updatePage();
                }}
            }}

            function changeZoom(value) {{
                const iframe = document.getElementById('pdf-viewer');
                iframe.style.transform = 'scale(' + value + ')';
                iframe.style.transformOrigin = 'top center';
            }}

            function downloadPDF() {{
                const link = document.createElement('a');
                link.href = pdfData;
                link.download = '{title}.pdf';
                link.click();
            }}

            // Keyboard navigation
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'ArrowLeft') previousPage();
                if (e.key === 'ArrowRight') nextPage();
                if (e.key === 'Escape') closeModal();
            }});
        </script>
    </body>
    </html>
    """
    return html


def render_pdf_modal(
    pdf_path: Optional[str] = None,
    pdf_data: Optional[bytes] = None,
    page: int = 1,
    title: str = "Document Viewer",
    height: int = 850,
    key: str = "pdf_modal",
) -> bool:
    """
    Render PDF modal with unified HTML structure.

    Args:
        pdf_path: Path to PDF file (optional if pdf_data provided)
        pdf_data: PDF bytes data (optional if pdf_path provided)
        page: Initial page to display
        title: Modal title
        height: Modal height in pixels
        key: Unique key for component

    Returns:
        True if modal is open, False otherwise
    """
    # Get PDF data
    if pdf_data is None and pdf_path:
        try:
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
        except Exception as e:
            st.error(f"Failed to read PDF: {e}")
            return False

    if pdf_data is None:
        st.error("No PDF data provided")
        return False

    # Encode PDF to base64
    pdf_base64 = base64.b64encode(pdf_data).decode("utf-8")

    # Generate HTML
    html_content = create_pdf_modal_html(
        pdf_base64=pdf_base64, page=page, title=title, modal_id=key
    )

    # Render modal using components.html
    result = components.html(html_content, height=height, scrolling=False)

    # Handle close message from JavaScript
    if result and isinstance(result, dict):
        if result.get("type") == "close-modal":
            return False

    return True


def show_pdf_modal_button(
    label: str,
    pdf_path: Optional[str] = None,
    pdf_data: Optional[bytes] = None,
    page: int = 1,
    title: str = "Document Viewer",
    key: str = None,
) -> bool:
    """
    Show a button that opens PDF modal when clicked.

    Args:
        label: Button label
        pdf_path: Path to PDF file
        pdf_data: PDF bytes data
        page: Page to display
        title: Modal title
        key: Button key

    Returns:
        True if modal should be shown
    """
    button_key = key or f"pdf_modal_btn_{hash(label)}"
    modal_key = f"{button_key}_modal"

    if st.button(label, key=button_key):
        st.session_state[modal_key] = True

    if st.session_state.get(modal_key, False):
        modal_open = render_pdf_modal(
            pdf_path=pdf_path, pdf_data=pdf_data, page=page, title=title, key=modal_key
        )

        if not modal_open:
            st.session_state[modal_key] = False
            st.rerun()

        return True

    return False
