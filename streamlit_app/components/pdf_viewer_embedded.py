"""
Embedded PDF Viewer Component
Renders PDF pages directly within a Streamlit column/container using native browser PDF rendering.
"""

import base64
import os
from pathlib import Path

import streamlit as st


def render_embedded_pdf_viewer():
    """
    Renders the PDF viewer content based on session state using an IFrame for native scrolling.
    """
    state = st.session_state.get("pdf_viewer_state", {})
    if not state.get("open"):
        return

    pdf_path = state.get("pdf_path", "")
    page_num = state.get("page", 1)
    doc_id = state.get("doc_id", "Document")

    # 1. Header
    c1, c2 = st.columns([8, 1])
    with c1:
        st.markdown(f"#### 📄 {doc_id}")
    with c2:
        if st.button("✖", key="close_pdf_panel_btn", help="Close PDF"):
            st.session_state.pdf_viewer_state["open"] = False
            st.rerun()

    # 2. Native PDF Embed
    if os.path.exists(pdf_path):
        try:
            with open(pdf_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode("utf-8")

            # Use standard object tag for PDF embedding (native browser viewer)
            # This supports scrolling, zooming, searching within PDF natively
            pdf_display = f"""
                <iframe
                    src="data:application/pdf;base64,{base64_pdf}#page={page_num}"
                    width="100%"
                    height="800px"
                    style="border: none; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                </iframe>
            """
            st.markdown(pdf_display, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Error loading PDF: {str(e)}")
    else:
        st.error(f"File not found: {pdf_path}")
