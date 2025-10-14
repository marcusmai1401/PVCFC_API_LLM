"""
🚀 PVCFC RAG System - Simplified UI

Production-grade retrieval-augmented question answering with citations.
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
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
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
    """Render the Home page with real API stats."""
    st.title("PVCFC RAG System")
    st.caption(
        "Production-grade retrieval-augmented question answering with citations and document grounding."
    )

    st.markdown("---")

    base = st.session_state.api_base_url

    # Check health
    health_ok = fetch_health(base)

    # Fetch index stats
    stats = None
    stats_ok = False
    if health_ok:
        with st.spinner("Loading index statistics..."):
            stats = fetch_index_stats(base)
            stats_ok = stats is not None

    # Display metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        backend_status = "✅ Healthy" if health_ok else "❌ Unreachable"
        st.metric("Backend Status", backend_status)

    with col2:
        if stats_ok:
            # Try various possible keys for document count
            doc_count = _get_first(
                stats,
                [
                    "document_count",
                    "total_documents",
                    "num_documents",
                    "bm25_num_docs",
                    "faiss_num_vectors",
                ],
            )
        else:
            doc_count = "—"
        st.metric("Documents Indexed", doc_count)

    with col3:
        if stats_ok:
            retriever_type = _get_first(
                stats,
                ["retriever_type", "retriever", "index_type", "mode"],
            )
        else:
            retriever_type = "—"
        st.metric("Retriever Type", retriever_type)

    st.markdown("---")

    # Show more details if available
    if stats_ok and stats:
        with st.expander("📊 Detailed Statistics", expanded=False):
            st.json(stats)

    if not health_ok:
        st.info(
            f"⚠️ The backend API is not reachable at `{base}`. "
            "Please verify the service is running and the URL is correct."
        )
        st.caption(
            "You can start the API with: `uvicorn app.main:app --host 127.0.0.1 --port 8000`"
        )


def show_query_lab():
    """Show the Query Lab (RAG QA) interface."""
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

    # Sidebar navigation
    with st.sidebar:
        st.markdown("# 🤖 PVCFC RAG")
        st.markdown("---")

        # Simple navigation - only 2 pages
        pages = ["🏠 Home", "🔬 RAG QA"]
        page = st.selectbox(
            "Navigate",
            pages,
            index=0,
            key="navigation",
        )

        st.markdown("---")

        # Minimal backend status indicator
        st.caption("**Backend**")
        base = st.session_state.api_base_url
        is_healthy = fetch_health(base, timeout=2)

        if is_healthy:
            st.success("✅ Healthy")
        else:
            st.warning("⚠️ Unreachable")

        st.caption(f"API: `{base}`")

        st.markdown("---")

        # Footer
        st.caption("PVCFC RAG System v0.6.1")
        st.caption("Simplified UI")

    # Route to selected page
    if page == "🏠 Home":
        show_home()
    elif page == "🔬 RAG QA":
        show_query_lab()


if __name__ == "__main__":
    main()
