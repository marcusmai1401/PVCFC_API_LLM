"""
PVCFC RAG System - iOS/macOS Style UI

Production-grade retrieval-augmented question answering with citations.
Clean, minimal iOS/macOS inspired interface with glassmorphism.
"""

import os
import sys
from pathlib import Path

import requests
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Page configuration
st.set_page_config(
    page_title="PVCFC RAG System",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize iOS/macOS theme
try:
    from streamlit_app.utils.theme import initialize_m3_theme

    initialize_m3_theme()
except ImportError:
    from utils.theme import initialize_m3_theme

    initialize_m3_theme()

# Additional iOS-specific styling
st.markdown(
    """
<style>
    /* Additional page-level iOS styling */
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 3rem !important;
        max-width: 1200px !important;
    }

    /* iOS-style dividers */
    hr {
        margin: 24px 0 !important;
        border: none !important;
        height: 0.5px !important;
        background: rgba(0, 0, 0, 0.08) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_session_state():
    """Initialize session state variables from environment."""
    if "api_base_url" not in st.session_state:
        # Read from environment with fallback to localhost
        st.session_state.api_base_url = os.getenv(
            "PVCFC_API_BASE_URL", "http://127.0.0.1:8000"
        )

    # Hardcoded feature flags for simplified UI
    st.session_state.enable_vision = True
    st.session_state.enable_embedding = True


def fetch_health(base: str, timeout: int = 3) -> bool:
    """Check if the API backend is healthy."""
    try:
        resp = requests.get(f"{base}/healthz", timeout=timeout)
        return resp.ok
    except Exception:
        return False


def fetch_index_stats(base: str, timeout: int = 5) -> dict:
    """Fetch index statistics from the API."""
    try:
        resp = requests.get(f"{base}/index-stats", timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _get_first(d: dict, keys: list, default: str = "—") -> str:
    """Extract the first available value from a dict given a list of keys."""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return str(d[k])
    return default


def show_home():
    """Render the Home page with iOS-styled system status."""
    # iOS-style hero header
    st.markdown(
        """
    <div class="ios-card" style="margin-bottom: 32px; text-align: center;">
        <h1 class="ios-title-large" style="margin: 0 0 12px 0;">PVCFC RAG System</h1>
        <p class="ios-body" style="margin: 0; color: #86868b;">
            Production-grade retrieval-augmented question answering with citations and document grounding
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Use system_status component for consistency
    try:
        from streamlit_app.components.system_status import render_system_status

        render_system_status(st.session_state.api_base_url)
    except ImportError:
        try:
            from components.system_status import render_system_status

            render_system_status(st.session_state.api_base_url)
        except Exception as e:
            # Fallback to simple display
            st.error(f"Could not load system status: {str(e)}")

            base = st.session_state.api_base_url
            health_ok = fetch_health(base)

            if health_ok:
                st.success("✅ Backend API is healthy")
            else:
                st.error(
                    f"❌ Backend API is not reachable at `{base}`. "
                    "Please verify the service is running."
                )


def show_query_lab():
    """Show the Query Lab (RAG QA) interface."""
    # Prefer the iOS/macOS minimal version
    try:
        from streamlit_app.components.query_lab_ios import render as query_lab_render

        query_lab_render()
        return
    except Exception:
        pass

    # Fallback to legacy component if iOS version not available
    try:
        from streamlit_app.components.query_lab import render as query_lab_render

        query_lab_render()
    except ImportError:
        try:
            from components.query_lab import render as query_lab_render

            query_lab_render()
        except Exception as e:
            st.error(f"❌ Error loading Query Lab: {str(e)}")
            st.info(
                "The Query Lab component is not available. "
                "Please check the components directory."
            )


def main():
    """Main application entry point."""

    # Initialize session state
    initialize_session_state()

    # Sidebar navigation with iOS styling
    with st.sidebar:
        st.markdown(
            """
        <div style="padding: 8px 0 24px 0;">
            <h1 class="ios-title" style="margin: 0;">PVCFC RAG</h1>
            <p class="ios-caption" style="margin: 8px 0 0 0;">Document Intelligence</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("<hr>", unsafe_allow_html=True)

        # Simple navigation - only 2 pages (no emojis for cleaner look)
        pages = ["Home", "RAG Query"]
        page = st.radio(
            "Navigate", pages, index=0, key="navigation", label_visibility="collapsed"
        )

        st.markdown("<hr>", unsafe_allow_html=True)

        # API Configuration
        st.markdown(
            '<p class="ios-caption" style="margin-bottom: 8px; text-transform: uppercase; font-weight: 600;">API Configuration</p>',
            unsafe_allow_html=True,
        )
        new_api_url = st.text_input(
            "API Base URL",
            value=st.session_state.api_base_url,
            key="api_url_input",
            label_visibility="collapsed",
            placeholder="http://127.0.0.1:8000",
            help="Backend API endpoint",
        )

        if new_api_url != st.session_state.api_base_url:
            st.session_state.api_base_url = new_api_url
            st.success("API URL updated")
            st.rerun()

        # Minimal backend status indicator
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            '<p class="ios-caption" style="margin-bottom: 12px; text-transform: uppercase; font-weight: 600;">System Status</p>',
            unsafe_allow_html=True,
        )
        base = st.session_state.api_base_url
        is_healthy = fetch_health(base, timeout=2)

        if is_healthy:
            st.markdown(
                """
            <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0;">
                <div class="ios-status-dot ios-status-healthy"></div>
                <span class="ios-body" style="font-weight: 500;">Healthy</span>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
            <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0;">
                <div class="ios-status-dot ios-status-error"></div>
                <span class="ios-body" style="font-weight: 500;">Offline</span>
            </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("<hr>", unsafe_allow_html=True)

        # Footer
        st.markdown(
            """
        <div style="margin-top: auto; padding-top: 24px;">
            <p class="ios-caption" style="margin: 0;">PVCFC RAG System v0.8.0</p>
            <p class="ios-caption" style="margin: 4px 0 0 0;">iOS/macOS Design</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Route to selected page
    if page == "Home":
        show_home()
    elif page == "RAG Query":
        show_query_lab()


if __name__ == "__main__":
    main()
