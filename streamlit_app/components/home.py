import os

import requests
import streamlit as st


def render_home():
    """
    Render the Premium Home Dashboard.
    """
    # 1. Hero Section
    st.markdown(
        """
        <div class="hero-container">
            <h1 style="font-size: 3rem; margin-bottom: 1rem;">
                Intelligent <span class="text-gradient">Knowledge Base</span>
            </h1>
            <p style="font-size: 1.2rem; color: var(--color-text-secondary); max-width: 600px; margin: 0 auto 2rem auto;">
                Access engineering data, P&ID drawings, and technical specifications through a unified AI-powered interface.
            </p>
            <div style="display: flex; justify-content: center; gap: 1rem;">
                <span class="badge blue">v2.0 Enterprise</span>
                <span class="badge green">System Active</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Feature Cards Grid
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            """
            <div class="feature-card">
                <div class="feature-icon-box">💬</div>
                <div class="feature-title">AI Engineering Assistant</div>
                <div class="feature-desc">
                    Context-aware chat interface capable of answering complex operational questions.
                    Supports cross-referencing multiple documents and citing specific pages.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Start Conversation",
            key="btn_home_chat",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.current_page = "chat"
            st.rerun()

    with col2:
        st.markdown(
            """
            <div class="feature-card">
                <div class="feature-icon-box">📂</div>
                <div class="feature-title">Document Repository</div>
                <div class="feature-desc">
                    Centralized explorer for P&ID drawings, datasheets, and manuals.
                    Filter by equipment tags, document types, or perform full-text search.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Browse Repository",
            key="btn_home_docs",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state.current_page = "documents"
            st.rerun()

    # 3. Stats Row (Mock data for visual density)
    st.markdown("<div style='margin-top: 3rem;'></div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Indexed Documents", "12,450", "+12 today")
    with c2:
        st.metric("P&ID Drawings", "856", "Updated 2h ago")
    with c3:
        st.metric("Equipment Tags", "45,200", "Synced")
    with c4:
        render_system_health_badge()


def render_system_health_badge():
    """Render a small health badge."""
    api_url = os.getenv("PVCFC_API_BASE_URL", "http://localhost:8000")
    try:
        resp = requests.get(f"{api_url}/healthz", timeout=1)
        is_healthy = resp.status_code == 200
    except:
        is_healthy = False

    color = "green" if is_healthy else "red"
    status = "Online" if is_healthy else "Offline"

    st.markdown(
        f"""
        <div style="background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 10px;">
            <div style="font-size: 0.75rem; color: var(--color-text-tertiary); margin-bottom: 4px;">API Status</div>
            <div style="display: flex; align-items: center; gap: 6px; font-weight: 600; font-size: 0.9rem;">
                <div style="width: 8px; height: 8px; border-radius: 50%; background-color: var(--color-{color});"></div>
                {status}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
