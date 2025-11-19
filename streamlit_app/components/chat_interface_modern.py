"""
Modern Chat Interface Component
Clean, enterprise-ready chat UI with citations and PDF viewer integration.
"""

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# Import Split View Controller
try:
    from streamlit_app.components.split_layout import open_pdf_panel
except ImportError:
    from components.split_layout import open_pdf_panel


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
            <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                <span class="badge gray">Equipment Specs</span>
                <span class="badge gray">Operating Procedures</span>
                <span class="badge gray">Safety Guidelines</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_message(msg: Dict):
    """Render a single chat message."""
    role = msg.get("role", "user")
    content = msg.get("content", "")
    citations = msg.get("citations", [])

    # Use CSS classes from modern.css
    css_class = "user" if role == "user" else "bot"
    avatar_icon = "👤" if role == "user" else "🤖"

    # Markdown HTML for the bubble
    html = f"""
    <div class="chat-bubble {css_class}">
        <div class="chat-avatar">{avatar_icon}</div>
        <div style="font-weight: 600; font-size: 0.85rem; color: var(--color-text-tertiary); margin-bottom: 0.5rem;">
            {role.upper()}
        </div>
        <div style="white-space: pre-wrap;">{content}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    # Render Citations (only for bot)
    if role == "assistant" and citations:
        # Render citations outside the bubble for cleaner look, but indented
        with st.container():
            col_spacer, col_content = st.columns([0.1, 0.9])
            with col_content:
                with st.expander(f"📚 Referenced Documents ({len(citations)})"):
                    for i, cit in enumerate(citations, 1):
                        doc_id = cit.get("doc_id", "Unknown Document")
                        page = cit.get("page", "?")
                        text = cit.get("text", "")[:120] + "..."
                        score = cit.get("score", 0)
                        pdf_path = cit.get("pdf_path", "")

                        # Citation Item Card
                        st.markdown(
                            f"""
                            <div style="padding: 10px; border-bottom: 1px solid var(--color-border); margin-bottom: 8px;">
                                <div style="font-weight: 600; color: var(--color-text-primary); display: flex; justify-content: space-between;">
                                    <span>[{i}] {doc_id}</span>
                                    <span class="badge gray">Page {page}</span>
                                </div>
                                <div style="font-size: 0.85rem; color: var(--color-text-secondary); margin: 4px 0;">
                                    "{text}"
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # View Button - Opens in Split Panel
                        if pdf_path:
                            if st.button(
                                "Open PDF",
                                key=f"cit_btn_{hash(content)}_{i}",
                                use_container_width=True,
                            ):
                                open_pdf_panel(pdf_path, page, doc_id)
                                st.rerun()


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
            padding: 1.5rem;
            z-index: 100;
            box-shadow: 0 -4px 20px rgba(0,0,0,0.05);
        ">
        </div>
        """,
        unsafe_allow_html=True,
    )

    # We can't put Streamlit widgets inside raw HTML divs easily, so we rely on standard flow
    # but the CSS above creates the visual "bar".
    # We just render the form normally at the bottom.

    with st.form(key="chat_form", clear_on_submit=True):
        col_in, col_btn = st.columns([6, 1])
        with col_in:
            user_input = st.text_input(
                "Message",
                placeholder="Type your question here...",
                label_visibility="collapsed",
                key="chat_input_field",
            )
        with col_btn:
            # Align button vertically
            st.markdown("<div style='height: 2px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "Send", type="primary", use_container_width=True
            )

    if submitted and user_input.strip():
        # Add user message
        st.session_state.conversation_history.append(
            {
                "role": "user",
                "content": user_input,
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
                st.session_state.conversation_history.append(
                    {
                        "role": "assistant",
                        "content": data.get("answer", ""),
                        "citations": data.get("citations", []),
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
        # Use a decent timeout
        resp = requests.post(endpoint, json=payload, timeout=60)
        if resp.status_code == 200:
            return {"success": True, "data": resp.json()}
        else:
            return {"success": False, "error": f"API {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
