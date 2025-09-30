"""
System Status Page
Full system status display with API health and index statistics
"""

import os
import sys

import streamlit as st

# Add parent directory to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from streamlit_app.components.system_status import render_system_status

# Page config
st.set_page_config(page_title="System Status", page_icon="📟", layout="wide")

st.title("📟 System Status Dashboard")
st.markdown("Monitor API health, index statistics, and component status")

# Get API URL from session state or default
api_base_url = st.session_state.get("api_base_url", "http://localhost:8000")

# API configuration
with st.expander("⚙️ API Configuration", expanded=False):
    new_api_url = st.text_input(
        "API Base URL", value=api_base_url, help="Base URL for the RAG API"
    )

    if new_api_url != api_base_url:
        st.session_state.api_base_url = new_api_url
        st.success("API URL updated. Click Refresh to check new status.")

# Render the full system status
render_system_status(st.session_state.get("api_base_url", "http://localhost:8000"))
