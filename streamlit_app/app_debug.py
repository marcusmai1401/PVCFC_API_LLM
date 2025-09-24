"""
PVCFC RAG Debug UI - Main Application
Purpose: Developer-focused frontend for debugging and optimizing RAG pipeline
Not for production use
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import components (will create these next)
from components import (
    dashboard,
    ingest_panel,
    metrics_logs,
    query_lab,
    report_lab,
    tier_inspector,
)

# Page configuration
st.set_page_config(
    page_title="PVCFC RAG Debug UI",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for developer-focused theme
st.markdown(
    """
<style>
    /* Developer theme - high contrast, monospace elements */
    .stApp {
        background-color: #1a1a1a;
    }

    /* Make code blocks more prominent */
    .stCodeBlock {
        background-color: #0d1117 !important;
        border: 1px solid #30363d;
    }

    /* Metric cards */
    [data-testid="metric-container"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #0d1117;
        border-radius: 5px;
    }

    /* Warning/Error styling */
    .warning-box {
        background-color: #3b2300;
        border: 1px solid #f85149;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }

    /* Success styling */
    .success-box {
        background-color: #0d2d1f;
        border: 1px solid #3fb950;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }

    /* Info boxes */
    .info-box {
        background-color: #161b22;
        border: 1px solid #388bfd;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }

    /* Monospace for technical data */
    .technical-data {
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 0.9em;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "api_base_url" not in st.session_state:
    # Default to localhost, can be overridden
    st.session_state.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

if "api_token" not in st.session_state:
    st.session_state.api_token = os.getenv("API_TOKEN", "")

if "current_trace_id" not in st.session_state:
    st.session_state.current_trace_id = None

if "request_history" not in st.session_state:
    st.session_state.request_history = []

# Sidebar configuration
with st.sidebar:
    st.title("🔧 Debug Configuration")

    # API Configuration section
    st.header("API Settings")

    # API Base URL
    new_base_url = st.text_input(
        "API Base URL",
        value=st.session_state.api_base_url,
        help="Base URL for RAG API (e.g., http://localhost:8000)",
    )
    if new_base_url != st.session_state.api_base_url:
        st.session_state.api_base_url = new_base_url
        st.success("API URL updated")

    # Optional API Token
    new_token = st.text_input(
        "API Token (optional)",
        value=st.session_state.api_token,
        type="password",
        help="Bearer token for protected endpoints",
    )
    if new_token != st.session_state.api_token:
        st.session_state.api_token = new_token
        st.success("Token updated")

    # Test connection
    if st.button("🔌 Test Connection"):
        import requests

        try:
            headers = {}
            if st.session_state.api_token:
                headers["Authorization"] = f"Bearer {st.session_state.api_token}"

            response = requests.get(
                f"{st.session_state.api_base_url}/healthz", headers=headers, timeout=5
            )

            if response.status_code == 200:
                health_data = response.json()
                st.success("✅ Connected")
                st.json(health_data)
            else:
                st.error(f"❌ Connection failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Connection error: {str(e)}")

    st.divider()

    # Feature Flags
    st.header("Feature Flags")

    # Vision Verification toggle
    st.session_state.enable_vision_verify = st.checkbox(
        "Enable Vision Verification",
        value=st.session_state.get("enable_vision_verify", False),
        help="Enable multimodal vision verification (requires page images)",
    )

    # Embedding view toggle
    st.session_state.enable_embedding_view = st.checkbox(
        "Enable Embedding View",
        value=st.session_state.get("enable_embedding_view", False),
        help="Show embedding visualizations (PCA/UMAP)",
    )

    # Debug verbosity
    st.session_state.debug_verbose = st.selectbox(
        "Debug Level",
        options=["normal", "verbose", "very_verbose"],
        index=0,
        help="Control amount of debug information shown",
    )

    st.divider()

    # Quick Stats
    st.header("Session Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Requests", len(st.session_state.request_history))
    with col2:
        if st.session_state.current_trace_id:
            st.caption(f"Trace: {st.session_state.current_trace_id[:8]}...")

    # Clear session
    if st.button("🗑️ Clear Session", type="secondary"):
        st.session_state.request_history = []
        st.session_state.current_trace_id = None
        st.rerun()

# Main content area
st.title("PVCFC RAG Debug UI")
st.caption("Developer interface for debugging and optimizing RAG pipeline performance")

# Navigation tabs
tab_dashboard, tab_query, tab_report, tab_ingest, tab_tier, tab_metrics = st.tabs(
    [
        "📊 Dashboard",
        "🔍 Query Lab",
        "📄 Report Lab",
        "📥 Ingest",
        "⚡ Tier Inspector",
        "📈 Metrics/Logs",
    ]
)

# Dashboard tab
with tab_dashboard:
    dashboard.render()

# Query Lab tab
with tab_query:
    query_lab.render()

# Report Lab tab
with tab_report:
    report_lab.render()

# Ingest tab
with tab_ingest:
    ingest_panel.render()

# Tier Inspector tab
with tab_tier:
    tier_inspector.render()

# Metrics/Logs tab
with tab_metrics:
    metrics_logs.render()

# Footer with connection status
st.divider()
footer_cols = st.columns([3, 1, 1])
with footer_cols[0]:
    st.caption(f"Connected to: {st.session_state.api_base_url}")
with footer_cols[1]:
    st.caption("Debug Mode: " + st.session_state.debug_verbose)
with footer_cols[2]:
    if st.button("🔄 Refresh", key="footer_refresh"):
        st.rerun()
