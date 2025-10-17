"""
Query Lab Component (iOS/macOS minimal, light-only)
- Clean layout, Inter font, glassmorphism
- Minimal icons (text-only), professional loading overlay
"""

import os
import time
from typing import Any, Dict

import pandas as pd
import requests
import streamlit as st

# Reuse existing API helper if available
try:
    from streamlit_app.components.query_lab import call_ask_api  # type: ignore
except Exception:

    def call_ask_api(
        query: str, api_base_url: str, params: Dict[str, Any], logger=None
    ) -> Dict[str, Any]:
        try:
            url = f"{api_base_url}/ask"
            payload = {
                "query": query,
                "hyde": params.get("hyde", True),
                "max_context": params.get("max_context", 8),
                "language": params.get("language", "vi"),
                "execution_mode": params.get("execution_mode", "production"),
            }
            resp = requests.post(url, json=payload, timeout=180)
            if resp.ok:
                data = resp.json()
                return {"success": True, "data": data}
            return {"success": False, "error": f"{resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def render(vision_mode: bool = False):
    # Session init
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = os.getenv(
            "PVCFC_API_BASE_URL", "http://127.0.0.1:8000"
        )
    if "query_results" not in st.session_state:
        st.session_state.query_results = None
    if "ios_loading" not in st.session_state:
        st.session_state.ios_loading = False

    # Header
    st.markdown(
        """
        <div class="ios-card" style="margin-bottom: 24px; text-align: center;">
          <h1 class="ios-title-large" style="margin: 0 0 8px 0;">Query Lab</h1>
          <p class="ios-body" style="margin: 0; color: #86868b;">Ask questions grounded in your documents</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Configuration")
        with st.expander("API", expanded=False):
            st.session_state.api_base_url = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url,
                placeholder="http://127.0.0.1:8000",
                label_visibility="visible",
            )
        query = st.text_area(
            "Your question",
            placeholder="Type your question...",
            height=120,
            label_visibility="visible",
        )
        lang = st.radio("Language", ["vi", "en"], horizontal=True, index=0)
        max_ctx = st.number_input("Context chunks", min_value=1, max_value=20, value=8)

        # Top linear loader when loading
        if st.session_state.ios_loading:
            st.markdown(
                '<div class="ios-linear-loader" style="margin: 8px 0 12px 0;"></div>',
                unsafe_allow_html=True,
            )

        if st.button("Run Query", type="primary", use_container_width=True):
            if not query:
                st.warning("Please enter a query")
            else:
                # Overlay ON
                st.session_state.ios_loading = True
                st.markdown(
                    """
                    <div class=\"ios-overlay\" role=\"status\" aria-live=\"polite\">
                      <div class=\"ios-overlay-content\">
                        <div class=\"ios-spinner\" style=\"margin: 0 auto;\"></div>
                        <p class=\"ios-caption\" style=\"margin: 12px 0 0 0;\">Generating answer...</p>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                params = {
                    "max_context": max_ctx,
                    "language": lang,
                    "execution_mode": "production",
                    "hyde": True,
                }
                result = call_ask_api(query, st.session_state.api_base_url, params)
                if result.get("success"):
                    st.session_state.query_results = result["data"]
                    st.session_state.ios_loading = False
                    st.rerun()
                else:
                    st.error(f"Error: {result.get('error')}")
                    st.session_state.ios_loading = False
                    st.rerun()

    with col2:
        st.subheader("Results")
        if not st.session_state.query_results:
            st.info("Results will appear here after running a query")
            return

        data = st.session_state.query_results
        tabs = st.tabs(
            ["Overview", "Retrieval", "Rerank", "Generation", "Metrics", "Raw Data"]
        )

        with tabs[0]:
            st.markdown("### Answer")
            answer = data.get("answer", "")
            if answer:
                st.markdown(answer)
            else:
                st.warning(
                    "No answer returned. Try rephrasing your question or check your index."
                )
            cols = st.columns(3)
            with cols[0]:
                st.metric("Confidence", f"{data.get('confidence', 0.0):.2%}")
            with cols[1]:
                st.metric("Citations", len(data.get("citations", [])))
            with cols[2]:
                st.metric("Latency", f"{data.get('total_latency_ms', 0):.0f}ms")

        with tabs[1]:
            st.markdown("### Retrieval Results")
            details = data.get("retrieval_details", {})
            st.json(details if details else {"message": "No retrieval details"})

        with tabs[2]:
            st.markdown("### Reranking Details")
            meta = data.get("meta", {})
            rerank = meta.get("rerank", {})
            st.json(rerank if rerank else {"message": "No rerank details"})

        with tabs[3]:
            st.markdown("### Generation Details")
            gen = data.get("generation_details", {}) or data.get("meta", {}).get(
                "generation", {}
            )
            st.json(gen if gen else {"message": "No generation details"})

        with tabs[4]:
            st.markdown("### Performance Metrics")
            breakdown = data.get("meta", {}).get("breakdown", {})
            if breakdown:
                for k, v in breakdown.items():
                    st.progress(
                        min(max(v, 0), 10000) / max(sum(breakdown.values()) or 1, 1)
                    )
                    st.caption(f"{k}: {v:.0f}ms")
            else:
                st.info("No timing data available")

        with tabs[5]:
            st.markdown("### Raw Response Data")
            st.json(data)
