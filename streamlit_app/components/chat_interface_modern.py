"""
Modern Chat Interface Component
Clean, enterprise-ready chat UI with citations and PDF viewer integration.
"""

import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# Import PDF Modal Controller (faster than split panel - uses API URL streaming)
try:
    from streamlit_app.components.pdf_viewer_modal import open_pdf_modal
    from streamlit_app.utils.citation_formatter import (
        convert_to_ieee_style,
        render_ieee_references,
    )
except ImportError:
    from components.pdf_viewer_modal import open_pdf_modal
    from utils.citation_formatter import convert_to_ieee_style, render_ieee_references


def render_chat_interface(api_base_url: str):
    """
    Main render function for the modern chat interface.
    """
    # 1. Header Area
    st.markdown(
        """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
            <div>
                <h2 style="margin: 0;">AI Engineering Assistant</h2>
                <p style="margin: 4px 0 0 0; color: var(--color-text-secondary);">Context-aware search across all plant documentation.</p>
            </div>
            <div style="text-align: right;">
                <span class="badge green">Online</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Session State Initialization
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    if "query_type" not in st.session_state:
        st.session_state.query_type = "technical_doc"

    # 3. Controls Bar
    with st.container():
        c1, c2, c3 = st.columns([2, 4, 1])
        with c1:
            # Mode Selector
            mode = st.selectbox(
                "Search Scope",
                options=["technical_doc", "pid"],
                format_func=lambda x: "📄 Technical Docs"
                if x == "technical_doc"
                else "🗺️ P&ID Drawings",
                label_visibility="collapsed",
            )
            if mode != st.session_state.query_type:
                st.session_state.query_type = mode
                # Optional: st.rerun() if immediate effect needed

        with c3:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.conversation_id = None
                st.session_state.conversation_history = []
                st.rerun()

    st.markdown(
        "<hr style='margin: 1rem 0; border-color: var(--color-border);'>",
        unsafe_allow_html=True,
    )

    # 4. Chat History
    chat_container = st.container()
    with chat_container:
        # Add padding to container
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)

        if not st.session_state.conversation_history:
            render_empty_state()
        else:
            for msg in st.session_state.conversation_history:
                render_message(msg)

        st.markdown("</div>", unsafe_allow_html=True)

    # 5. Input Area (Sticky Bottom)
    st.markdown("<div style='height: 120px;'></div>", unsafe_allow_html=True)
    render_input_area(api_base_url)


def render_empty_state():
    """Render a helpful empty state."""
    st.markdown(
        """
        <div style="text-align: center; padding: 4rem 2rem; color: var(--color-text-tertiary);">
            <div style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.5;">💬</div>
            <h3 style="color: var(--color-text-secondary);">Ready to assist</h3>
            <p style="max-width: 400px; margin: 0 auto 2rem auto;">
                I can help you find information in technical manuals, datasheets, and locate equipment on P&ID drawings.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_message(msg: Dict):
    """Render a single chat message with IEEE-style citations."""
    role = msg.get("role", "user")
    content = msg.get("content", "")
    citations = msg.get("citations", [])
    doc_number_map = msg.get("doc_number_map", {})

    # Use CSS classes from modern.css
    css_class = "user" if role == "user" else "bot"
    avatar_icon = "👤" if role == "user" else "🤖"

    # Convert to IEEE style for assistant messages
    display_content = content
    ieee_refs = []
    if role == "assistant" and citations:
        display_content, ieee_refs = convert_to_ieee_style(
            content, citations, doc_number_map
        )

    # Clean excessive newlines to compact the display
    if display_content:
        # Replace 3 or more newlines with 2
        display_content = re.sub(r"\n{3,}", "\n\n", display_content)
        display_content = display_content.strip()

    # Markdown HTML for the bubble
    # Inject CSS for compact spacing inside bubbles
    st.markdown(
        """
        <style>
        .chat-bubble p {
            margin-bottom: 0.25rem !important;
            line-height: 1.5 !important;
        }
        .chat-bubble ul, .chat-bubble ol {
            margin-top: 0.25rem !important;
            margin-bottom: 0.25rem !important;
            padding-left: 1.2rem !important;
        }
        .chat-bubble li {
            margin-bottom: 0.1rem !important;
            line-height: 1.5 !important;
        }
        .chat-bubble h1, .chat-bubble h2, .chat-bubble h3, .chat-bubble h4, .chat-bubble h5, .chat-bubble h6 {
            margin-top: 0.5rem !important;
            margin-bottom: 0.25rem !important;
        }
        .chat-bubble .katex-display {
            margin: 0.25rem 0 !important;
        }
        /* Reduce spacing between blocks */
        .chat-bubble > div > p:empty {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    html = f"""
    <div class="chat-bubble {css_class}">
        <div class="chat-avatar">{avatar_icon}</div>
        <div style="font-weight: 600; font-size: 0.85rem; color: var(--color-text-tertiary); margin-bottom: 0.5rem;">
            {role.upper()}
        </div>
        <div style="white-space: pre-wrap;">{display_content}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    # Render IEEE References (only for bot with citations)
    if role == "assistant" and ieee_refs:
        with st.container():
            # Removed spacer columns to ensure left alignment
            st.markdown("**Nguồn:**")

            # Inject CSS for STRICT left-aligned text-like buttons
            st.markdown(
                """
                <style>
                /* Target tertiary buttons specifically in this context */
                div[data-testid="stVerticalBlock"] button[kind="tertiary"] {
                    justify-content: flex-start !important;
                    text-align: left !important;
                    padding-left: 0 !important;
                    padding-right: 0 !important;
                    border: none !important;
                    color: #4f46e5 !important;
                    background: transparent !important;
                    box-shadow: none !important;
                    height: auto !important;
                    min-height: 0 !important;
                    margin-bottom: 2px !important;
                    width: 100% !important;
                }

                /* Target the inner markdown container to force left align */
                div[data-testid="stVerticalBlock"] button[kind="tertiary"] div[data-testid="stMarkdownContainer"] p {
                    text-align: left !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                div[data-testid="stVerticalBlock"] button[kind="tertiary"]:hover {
                    text-decoration: underline !important;
                    color: #4338ca !important;
                    background-color: transparent !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            for ref in ieee_refs:
                ref_num = ref.get("ref_num", "?")
                file_name = ref.get("file_name", "Unknown")
                pages = ref.get("pages", [])
                pdf_path = ref.get("pdf_path", "")

                # Format pages string
                pages_str = ", ".join(str(p) for p in sorted(pages)) if pages else ""

                # Label: [1] Filename.pdf, trang 1, 2
                label = f"[{ref_num}] {file_name}"
                if pages_str:
                    label += f", trang {pages_str}"

                # Clickable Text Link (using tertiary button)
                if st.button(
                    label,
                    key=f"ref_link_{hash(content)}_{ref_num}",
                    type="tertiary",
                    use_container_width=True,
                ):
                    if pdf_path:
                        first_page = sorted(pages)[0] if pages else 1
                        open_pdf_modal(pdf_path, first_page, file_name)
                        st.rerun()
                    else:
                        st.toast(
                            f"⚠️ Không tìm thấy file PDF cho tài liệu: {file_name}"
                        )


def render_input_area(api_base_url: str):
    """Render the input form."""
    # Use a container with top border to separate input
    st.markdown(
        """
        <div style="
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: white;
            border-top: 1px solid var(--color-border);
            padding: 1rem;
            z-index: 100;
            box-shadow: 0 -4px 20px rgba(0,0,0,0.05);
        ">
        </div>
        """,
        unsafe_allow_html=True,
    )

    # st.chat_input handles the UI and submission automatically
    # It stays at the bottom and expands as needed
    if prompt := st.chat_input("Type your question here..."):
        # Add user message
        st.session_state.conversation_history.append(
            {
                "role": "user",
                "content": prompt,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        st.session_state.is_processing = True
        st.rerun()

    # Processing Logic (runs after rerun)
    if st.session_state.is_processing:
        with st.spinner("Analyzing documents..."):
            response = call_api(
                query=st.session_state.conversation_history[-1]["content"],
                api_base_url=api_base_url,
                conversation_id=st.session_state.conversation_id,
                query_type=st.session_state.query_type,
            )

            if response.get("success"):
                data = response["data"]
                st.session_state.conversation_id = data.get("conversation_id")

                # Extract doc_number_map from metadata
                doc_number_map = {}
                meta = data.get("meta", {})
                if meta.get("doc_number_map"):
                    doc_number_map = meta.get("doc_number_map")
                elif meta.get("vision_generation", {}).get("doc_number_map"):
                    doc_number_map = meta.get("vision_generation", {}).get(
                        "doc_number_map"
                    )

                st.session_state.conversation_history.append(
                    {
                        "role": "assistant",
                        "content": data.get("answer", ""),
                        "citations": data.get("citations", []),
                        "doc_number_map": doc_number_map,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
            else:
                # Add error message
                st.session_state.conversation_history.append(
                    {
                        "role": "assistant",
                        "content": f"⚠️ Error: {response.get('error')}",
                        "citations": [],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            st.session_state.is_processing = False
            st.rerun()


def call_api(
    query: str,
    api_base_url: str,
    conversation_id: str = None,
    query_type: str = "technical_doc",
) -> Dict:
    """Call the backend API."""
    try:
        endpoint = f"{api_base_url.rstrip('/')}/ask"
        payload = {
            "query": query,
            "query_type": query_type,
            "conversation_id": conversation_id,
            "max_context": 5,
        }
        # Use a decent timeout (300s for Vision AI with 20-30 pages)
        resp = requests.post(endpoint, json=payload, timeout=300)
        if resp.status_code == 200:
            return {"success": True, "data": resp.json()}
        else:
            return {"success": False, "error": f"API {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
