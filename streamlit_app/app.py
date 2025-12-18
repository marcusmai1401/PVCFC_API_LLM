"""
PVCFC Intelligent Search System
Modern Enterprise UI for RAG and Document Management.
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Page Config
st.set_page_config(
    page_title="PVCFC Intelligent Search",
    page_icon="🔹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import Components
try:
    from streamlit_app.components.chat_interface_modern import render_chat_interface
    from streamlit_app.components.deep_search import render as render_deep_search
    from streamlit_app.components.home import render_home
    from streamlit_app.components.pdf_viewer_embedded import render_embedded_pdf_viewer
    from streamlit_app.components.pdf_viewer_modal import render_pdf_viewer_modal
    from streamlit_app.components.split_layout import render_split_view
except ImportError:
    # Fallback for direct running
    from components.chat_interface_modern import render_chat_interface
    from components.deep_search import render as render_deep_search
    from components.home import render_home
    from components.pdf_viewer_embedded import render_embedded_pdf_viewer
    from components.pdf_viewer_modal import render_pdf_viewer_modal
    from components.split_layout import render_split_view


def load_css():
    """Load the premium design system."""
    css_path = Path(__file__).parent / "styles" / "modern.css"
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def init_session_state():
    """Initialize global session state."""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "deep_search"

    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = os.getenv(
            "PVCFC_API_BASE_URL", "http://localhost:8000"
        )

    if "pdf_viewer_state" not in st.session_state:
        st.session_state.pdf_viewer_state = {"open": False}


def render_sidebar():
    """Render the premium app sidebar."""
    with st.sidebar:
        # Brand Header
        st.markdown(
            """
            <div style="padding: 0 0.5rem 1.5rem 0.5rem;">
                <div style="font-weight: 800; font-size: 1.8rem; color: var(--color-text-primary); letter-spacing: -0.03em;">
                    <span style="color: #00904a;">PVCFC</span> Search
                </div>
                <div style="font-size: 1rem; color: var(--color-text-secondary); font-weight: 600;">
                    Engineering Intelligence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Navigation Section
        st.markdown('<div class="nav-section">PLATFORM</div>', unsafe_allow_html=True)

        nav_items = [
            {"id": "deep_search", "icon": "🔍", "label": "Deep Search"},
            {"id": "chat", "icon": "💬", "label": "AI Assistant"},
        ]

        for item in nav_items:
            is_active = st.session_state.current_page == item["id"]
            active_class = "active" if is_active else ""

            if st.button(
                f"{item['icon']}  {item['label']}",
                key=f"nav_{item['id']}",
                use_container_width=True,
                type="secondary" if not is_active else "primary",
            ):
                st.session_state.current_page = item["id"]
                # Close PDF on nav change to keep view clean, or keep it?
                # Let's keep it open if they navigate, except Home.
                if item["id"] == "home":
                    st.session_state.pdf_viewer_state["open"] = False
                st.rerun()

        # Footer Profile & University Info
        logo_path = Path(__file__).parent / "assets" / "logo_hcmut.png"
        logo_html = ""
        if logo_path.exists():
            import base64

            with open(logo_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            logo_html = f'<img src="data:image/png;base64,{img_data}" style="width: 120px; height: auto; margin-bottom: 10px;">'

        st.markdown(
            f"""
            <div style="margin-top: auto; padding-top: 2rem; border-top: 1px solid var(--color-border);">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1.5rem;">
                    <div style="width: 32px; height: 32px; background: #e2e8f0; border-radius: 50%; display: flex; align-items: center; justify-content: center;">U</div>
                    <div>
                        <div style="font-size: 0.85rem; font-weight: 600;">Engineer User</div>
                        <div style="font-size: 0.75rem; color: var(--color-text-tertiary);">admin@pvcfc.com</div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 1rem;">
                    {logo_html}
                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--color-text-primary); margin-bottom: 4px;">Mai Thái Bảo</div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--color-text-primary);">Trần Quốc Bảo</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main():
    # 1. Setup
    init_session_state()
    load_css()

    # 2. Sidebar
    render_sidebar()

    # 3. Main Content Routing
    page = st.session_state.current_page

    # Wrapper functions for split view compatibility
    def content_home():
        render_home()

    def content_chat():
        render_chat_interface(st.session_state.api_base_url)

    def content_deep_search():
        render_deep_search()

    # Route
    if page == "home":
        # Home always full width
        content_home()
    elif page == "chat":
        render_split_view(content_chat, render_embedded_pdf_viewer)
    elif page == "deep_search":
        # Deep Search with PDF viewer integration
        render_split_view(content_deep_search, render_embedded_pdf_viewer)

    # Render PDF modal if open (for document preview)
    render_pdf_viewer_modal()


if __name__ == "__main__":
    main()
