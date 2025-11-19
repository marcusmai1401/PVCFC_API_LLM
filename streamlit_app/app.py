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
    from streamlit_app.components.doc_browser import render_doc_browser
    from streamlit_app.components.home import render_home
    from streamlit_app.components.pdf_viewer_embedded import render_embedded_pdf_viewer
    from streamlit_app.components.split_layout import render_split_view
except ImportError:
    # Fallback for direct running
    from components.chat_interface_modern import render_chat_interface
    from components.doc_browser import render_doc_browser
    from components.home import render_home
    from components.pdf_viewer_embedded import render_embedded_pdf_viewer
    from components.split_layout import render_split_view


def load_css():
    """Load the premium design system."""
    css_path = Path(__file__).parent / "styles" / "modern.css"
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def init_session_state():
    """Initialize global session state."""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "home"

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
                <div style="font-weight: 800; font-size: 1.4rem; color: var(--color-text-primary); letter-spacing: -0.03em;">
                    <span style="color: var(--color-brand);">PVCFC</span> Search
                </div>
                <div style="font-size: 0.8rem; color: var(--color-text-tertiary); font-weight: 500;">
                    Engineering Intelligence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Navigation Section
        st.markdown('<div class="nav-section">PLATFORM</div>', unsafe_allow_html=True)

        nav_items = [
            {"id": "home", "icon": "🏠", "label": "Overview"},
            {"id": "chat", "icon": "💬", "label": "AI Assistant"},
            {"id": "documents", "icon": "📂", "label": "Repository"},
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

        # Tools Section
        st.markdown('<div class="nav-section">TOOLS</div>', unsafe_allow_html=True)
        st.button(
            "⚙️ Settings", key="nav_settings", use_container_width=True, disabled=True
        )
        st.button(
            "📊 Analytics", key="nav_analytics", use_container_width=True, disabled=True
        )

        # Footer Profile
        st.markdown(
            """
            <div style="margin-top: auto; padding-top: 2rem; border-top: 1px solid var(--color-border);">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="width: 32px; height: 32px; background: #e2e8f0; border-radius: 50%; display: flex; align-items: center; justify-content: center;">👤</div>
                    <div>
                        <div style="font-size: 0.85rem; font-weight: 600;">Engineer User</div>
                        <div style="font-size: 0.75rem; color: var(--color-text-tertiary);">admin@pvcfc.com</div>
                    </div>
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

    def content_docs():
        render_doc_browser()

    # Route
    if page == "home":
        # Home always full width
        content_home()
    elif page == "chat":
        render_split_view(content_chat, render_embedded_pdf_viewer)
    elif page == "documents":
        render_split_view(content_docs, render_embedded_pdf_viewer)


if __name__ == "__main__":
    main()
