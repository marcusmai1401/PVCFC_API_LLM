"""
Side Sheet Component for Material Design 3
Provides modal drawer for displaying citations and PDF previews
"""

from typing import Dict, List, Optional

import streamlit as st


def render_side_sheet_js():
    """Inject JavaScript for side sheet control."""
    js_code = """
    <script>
    function openSideSheet(sheetId) {
        const sheet = document.getElementById(sheetId);
        const scrim = document.getElementById(sheetId + '-scrim');
        if (sheet && scrim) {
            sheet.classList.add('md-side-sheet-open');
            scrim.classList.add('md-side-sheet-scrim-visible');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeSideSheet(sheetId) {
        const sheet = document.getElementById(sheetId);
        const scrim = document.getElementById(sheetId + '-scrim');
        if (sheet && scrim) {
            sheet.classList.remove('md-side-sheet-open');
            scrim.classList.remove('md-side-sheet-scrim-visible');
            document.body.style.overflow = '';
        }
    }

    // Close on scrim click
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('md-side-sheet-scrim-visible')) {
            const sheetId = e.target.id.replace('-scrim', '');
            closeSideSheet(sheetId);
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openSheet = document.querySelector('.md-side-sheet-open');
            if (openSheet) {
                const sheetId = openSheet.id;
                closeSideSheet(sheetId);
            }
        }
    });
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)


def render_side_sheet(
    sheet_id: str,
    title: str,
    content_html: str,
    is_open: bool = False,
):
    """
    Render a Material Design 3 side sheet modal.

    Args:
        sheet_id: Unique identifier for the side sheet
        title: Header title
        content_html: HTML content to display in the sheet
        is_open: Whether the sheet should be initially open
    """

    open_class = "md-side-sheet-open" if is_open else ""
    scrim_class = "md-side-sheet-scrim-visible" if is_open else ""

    side_sheet_html = f"""
    <!-- Scrim (overlay) -->
    <div id="{sheet_id}-scrim" class="md-side-sheet-scrim {scrim_class}"></div>

    <!-- Side Sheet -->
    <div id="{sheet_id}" class="md-side-sheet {open_class}">
        <div class="md-side-sheet-header">
            <h2 class="md-side-sheet-header-title">{title}</h2>
            <button
                class="md-icon-button"
                onclick="closeSideSheet('{sheet_id}')"
                aria-label="Close side sheet"
            >
                <span class="material-symbols-outlined">close</span>
            </button>
        </div>
        <div class="md-side-sheet-content">
            {content_html}
        </div>
    </div>
    """

    st.markdown(side_sheet_html, unsafe_allow_html=True)


def render_citation_side_sheet(
    citations: List[Dict],
    api_base_url: str,
    selected_citation_idx: Optional[int] = None,
):
    """
    Render a side sheet specifically for citations.

    Args:
        citations: List of citation dictionaries
        api_base_url: Base URL for API (for PDF viewer)
        selected_citation_idx: Index of selected citation (if any)
    """

    # Build citations list HTML
    citations_html = ""

    for idx, citation in enumerate(citations):
        doc_id = citation.get("doc_id", "Unknown")
        page = citation.get("page", "N/A")
        score = citation.get("score", 0)
        confidence = citation.get("confidence", citation.get("relevance_score", 0))
        text = citation.get("text", citation.get("text_snippet", ""))
        pdf_path = citation.get("pdf_path", "")

        # Extract clean file name
        file_name = doc_id
        if pdf_path:
            from pathlib import Path

            file_name = Path(pdf_path).name
        elif doc_id.startswith("DOCID_"):
            parts = doc_id.split("_")
            file_name = (
                "_".join(parts[1:-1])
                if len(parts) > 2
                else parts[1]
                if len(parts) > 1
                else doc_id
            )

        # Build PDF link
        pdf_link = ""
        if pdf_path and page:
            from urllib.parse import urlencode

            params = {
                "pdf_path": pdf_path,
                "page_num": str(page),
                "dpi": "200",
                "format": "png",
            }
            params_str = urlencode(params)
            pdf_link = f"{api_base_url}/api/pdf/render-page?{params_str}"

        # Score display
        score_display = f"{score:.3f}" if isinstance(score, (int, float)) else "N/A"
        conf_display = (
            f"{confidence:.3f}" if isinstance(confidence, (int, float)) else "N/A"
        )

        citations_html += f"""
        <div class="md-citation-item">
            <div class="md-citation-item-header">
                <span class="md-citation-item-title">#{idx + 1} {file_name}</span>
                <span class="md-citation-item-meta">Page {page}</span>
            </div>
            <div style="display: flex; gap: 16px; margin-bottom: 8px;">
                <span class="md-citation-item-meta">Score: {score_display}</span>
                <span class="md-citation-item-meta">Conf: {conf_display}</span>
            </div>
            {f'<div class="md-citation-item-text">{text[:200]}...</div>' if text else ''}
            {f'<a href="{pdf_link}" target="_blank" class="md-button-text" style="margin-top: 8px; display: inline-flex; align-items: center; gap: 4px;"><span class="material-symbols-outlined md-18">visibility</span> View Page</a>' if pdf_link else ''}
        </div>
        """

    if not citations_html:
        citations_html = '<p class="md-typescale-body-medium" style="color: var(--md-sys-color-on-surface-variant);">No citations available</p>'

    # Render the side sheet
    is_open = selected_citation_idx is not None
    render_side_sheet(
        sheet_id="citations-side-sheet",
        title=f"Citations ({len(citations)})",
        content_html=citations_html,
        is_open=is_open,
    )
