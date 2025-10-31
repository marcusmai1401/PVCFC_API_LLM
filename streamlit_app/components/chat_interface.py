"""
ChatGPT-style chat interface component.

Clean, minimal chat UI with:
- Message bubbles (user: blue right, bot: gray left)
- Typing indicator during responses
- Auto-scroll to bottom
- Expandable citations
- Sticky input at bottom
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from streamlit_app.components.typing_indicator import render_typing_indicator


def render_message_bubble(
    role: str,
    content: str,
    citations: Optional[List[Dict]] = None,
    metadata: Optional[Dict] = None,
    timestamp: Optional[str] = None,
):
    """
    Render a single message bubble.

    Args:
        role: "user" or "assistant"
        content: Message text
        citations: List of citations (for bot messages)
        metadata: Message metadata (model, confidence, etc.)
        timestamp: ISO timestamp
    """
    # Prepare metadata tooltip
    tooltip_parts = []
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            tooltip_parts.append(dt.strftime("%H:%M"))
        except:
            pass
    if metadata:
        if "model" in metadata:
            tooltip_parts.append(f"Model: {metadata['model']}")
        if "confidence" in metadata:
            tooltip_parts.append(f"Confidence: {metadata['confidence']:.0%}")

    tooltip_text = " | ".join(tooltip_parts) if tooltip_parts else ""

    # CSS class based on role
    bubble_class = "message-bubble-user" if role == "user" else "message-bubble-bot"
    wrapper_class = "user" if role == "user" else "bot"

    # Render message
    st.markdown(
        f"""
        <div class="message-wrapper {wrapper_class}">
            <div class="message-bubble {bubble_class}">
                <div class="message-content">{content}</div>
                {f'<div class="message-metadata">{tooltip_text}</div>' if tooltip_text else ''}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render citations if available (bot messages only)
    if role == "assistant" and citations:
        render_citations_expander(citations)


def render_citations_expander(citations: List[Dict]):
    """
    Render expandable citations section under bot message.

    Args:
        citations: List of citation objects
    """
    if not citations:
        return

    # Use expander for citations
    with st.expander(f"📚 Citations ({len(citations)})", expanded=False):
        for i, citation in enumerate(citations, 1):
            doc_id = citation.get("doc_id", "Unknown")
            page = citation.get("page", "?")
            pdf_path = citation.get("pdf_path", "")
            confidence = citation.get("confidence")

            # Extract filename from path
            filename = pdf_path.split("\\")[-1] if pdf_path else doc_id

            # Citation info columns
            cit_col1, cit_col2 = st.columns([3, 1])

            with cit_col1:
                # Build citation display
                st.markdown(
                    f"""
                    **[{i}]** {filename} - Page {page}
                    {f"(Confidence: {confidence:.0%})" if confidence else ""}
                    """,
                    unsafe_allow_html=True,
                )

            with cit_col2:
                # ISSUE 5 FIX: Enable "View Page" button with PyMuPDF support
                if pdf_path:
                    if st.button(
                        f"🔍 View",
                        key=f"view_{doc_id}_{page}_{i}",
                        use_container_width=True,
                    ):
                        # Open enhanced PDF modal that can show specific pages
                        try:
                            from streamlit_app.components.pdf_page_viewer import (
                                open_pdf_modal,
                            )
                        except ImportError:
                            try:
                                from components.pdf_page_viewer import open_pdf_modal
                            except ImportError:
                                # Fallback to basic modal
                                from streamlit_app.components.pdf_viewer_modal import (
                                    open_pdf_modal,
                                )

                        # Open modal with specific page
                        open_pdf_modal(pdf_path, page, filename)
                        st.rerun()


def render_chat_messages(
    messages: List[Dict], max_display: int = 20, show_load_more: bool = True
):
    """
    Render chat message history.

    Args:
        messages: List of message dicts with role, content, citations, metadata
        max_display: Maximum messages to display (pagination)
        show_load_more: Show "Load earlier" button
    """
    # Initialize message offset in session state
    if "message_offset" not in st.session_state:
        st.session_state.message_offset = 0

    total_messages = len(messages)
    offset = st.session_state.message_offset

    # Calculate which messages to display
    start_idx = max(0, total_messages - max_display - offset)
    end_idx = total_messages - offset
    visible_messages = messages[start_idx:end_idx]

    # Show "Load earlier" button if there are older messages
    if start_idx > 0 and show_load_more:
        if st.button(
            f"↑ Load earlier messages ({start_idx} more)",
            key="load_more_btn",
            use_container_width=True,
        ):
            st.session_state.message_offset += max_display
            st.rerun()

    # Render visible messages
    for msg in visible_messages:
        render_message_bubble(
            role=msg.get("role", "user"),
            content=msg.get("content", ""),
            citations=msg.get("citations"),
            metadata=msg.get("metadata"),
            timestamp=msg.get("timestamp"),
        )


def render_sticky_input(
    api_base_url: str,
    request_in_flight: bool = False,
    placeholder: str = "Type your message...",
):
    """
    Render sticky input box at bottom with Send button.

    Args:
        api_base_url: API endpoint URL
        request_in_flight: Whether a request is currently being processed
        placeholder: Input placeholder text

    Returns:
        User query if submitted, None otherwise
    """
    # ISSUE 2 & 3 FIX: Show spinner, don't disable input, prevent double-submit

    # Create form for input
    with st.form(key="chat_input_form", clear_on_submit=True):
        col1, col2 = st.columns([6, 1])

        with col1:
            # ISSUE 2: Fixed container with proper relative positioning
            input_container = st.container()
            with input_container:
                # Never disable input field (keep it interactive)
                user_input = st.text_area(
                    "Message",
                    placeholder=placeholder,
                    height=60,
                    max_chars=2000,
                    disabled=False,  # Always enabled
                    label_visibility="collapsed",
                    key="chat_input_text",
                )

                # Show spinner when processing (fixed position in viewport)
                if request_in_flight:
                    st.markdown(
                        """
                        <style>
                        .pvcfc-input-spinner {
                            position: fixed;
                            bottom: 85px;
                            right: 100px;
                            width: 24px;
                            height: 24px;
                            z-index: 1000;
                        }
                        .pvcfc-input-spinner::after {
                            content: "";
                            display: block;
                            width: 20px;
                            height: 20px;
                            border: 3px solid #0066cc;
                            border-radius: 50%;
                            border-top-color: transparent;
                            animation: spinner-rotate 0.8s linear infinite;
                        }
                        @keyframes spinner-rotate {
                            to { transform: rotate(360deg); }
                        }
                        </style>
                        <div class="pvcfc-input-spinner"></div>
                        """,
                        unsafe_allow_html=True,
                    )

        with col2:
            # Align button to bottom
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

            # ISSUE 2 & 3: Button with pointer-events control
            button_label = "⏳ Sending..." if request_in_flight else "📤 Send"

            # Add CSS class to disable pointer-events when locked
            button_css = ""
            if request_in_flight:
                button_css = """
                <style>
                button[kind="primary"][data-testid="baseButton-primary"] {
                    pointer-events: none !important;
                    opacity: 0.7 !important;
                    cursor: not-allowed !important;
                }
                </style>
                """
                st.markdown(button_css, unsafe_allow_html=True)

            submit = st.form_submit_button(
                button_label,
                disabled=False,  # Don't use HTML disabled (keeps color)
                use_container_width=True,
                type="primary",
            )

        # ISSUE 3 FIX: Check request lock before processing
        if submit and user_input and user_input.strip():
            if not request_in_flight:
                return user_input.strip()
            else:
                # Silently ignore if already processing
                return None

    return None


def auto_scroll_script():
    """
    JavaScript to auto-scroll chat container to bottom.
    """
    # Use unique key to force re-execution on each rerun
    scroll_key = int(time.time() * 1000)

    st.markdown(
        f"""
        <script id="scroll-script-{scroll_key}">
        // Auto-scroll to bottom
        function scrollToBottom() {{
            // Find main content area
            const mainBlock = window.parent.document.querySelector('.main .block-container');
            if (mainBlock) {{
                mainBlock.scrollTop = mainBlock.scrollHeight;
            }}

            // Also try vertical block
            const vertBlock = window.parent.document.querySelector('[data-testid="stVerticalBlock"]');
            if (vertBlock) {{
                vertBlock.scrollTop = vertBlock.scrollHeight;
            }}
        }}

        // Scroll multiple times to ensure it works
        setTimeout(scrollToBottom, 100);
        setTimeout(scrollToBottom, 300);
        setTimeout(scrollToBottom, 500);
        </script>
        """,
        unsafe_allow_html=True,
    )


def render(api_base_url: str = "http://127.0.0.1:8000"):
    """
    Main render function for ChatGPT-style chat interface.

    Args:
        api_base_url: Base URL for API endpoints
    """
    # CSS is already loaded by theme.py, no need to load again
    # Just add any page-specific overrides if needed
    st.markdown(
        """
        <style>
        /* Page-specific overrides for chat */
        .block-container {
            padding-bottom: 120px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False

    # ISSUE 3 FIX: Add request lock and debounce
    if "request_in_flight" not in st.session_state:
        st.session_state.request_in_flight = False
    if "last_submit_ts" not in st.session_state:
        st.session_state.last_submit_ts = 0

    if "query_type" not in st.session_state:
        st.session_state.query_type = "technical_doc"  # Default to technical docs

    # ISSUE 1 FIX: iOS-style segmented control for Document Type
    st.markdown(
        '<p class="ios-caption" style="margin: 0 0 8px 0; text-transform: uppercase; font-weight: 600;">Document Type</p>',
        unsafe_allow_html=True,
    )

    # Custom segmented control using columns
    col1, col2 = st.columns(2)

    query_type_options = [
        {"label": "📄 Technical Documents", "value": "technical_doc"},
        {"label": "🗺️ P&ID Diagrams", "value": "pid"},
    ]

    current_type = st.session_state.query_type

    # Wrap in container for styling
    st.markdown('<div class="pvcfc-segmented-control-wrapper">', unsafe_allow_html=True)

    with col1:
        tech_class = (
            "pvcfc-segment pvcfc-segment-active"
            if current_type == "technical_doc"
            else "pvcfc-segment"
        )
        if st.button(
            "📄 Technical Documents",
            key="seg_tech",
            use_container_width=True,
            type="primary" if current_type == "technical_doc" else "secondary",
        ):
            if current_type != "technical_doc":
                st.session_state.query_type = "technical_doc"
                st.session_state.conversation_id = None
                st.session_state.conversation_history = []
                st.rerun()

    with col2:
        pid_class = (
            "pvcfc-segment pvcfc-segment-active"
            if current_type == "pid"
            else "pvcfc-segment"
        )
        if st.button(
            "🗺️ P&ID Diagrams",
            key="seg_pid",
            use_container_width=True,
            type="primary" if current_type == "pid" else "secondary",
        ):
            if current_type != "pid":
                st.session_state.query_type = "pid"
                st.session_state.conversation_id = None
                st.session_state.conversation_history = []
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin: 16px 0;'>", unsafe_allow_html=True)

    # Main chat area
    chat_container = st.container()

    with chat_container:
        # Show empty state if no messages
        if not st.session_state.conversation_history:
            # Update empty state based on query_type
            if st.session_state.query_type == "pid":
                icon = "🗺️"
                hint_text = (
                    "Ask about P&ID diagrams, equipment tags, and piping systems"
                )
            else:
                icon = "📄"
                hint_text = "Ask about technical documents, manuals, and specifications"

            st.markdown(
                f"""
                <div class="empty-state">
                    <div class="empty-state-icon">{icon}</div>
                    <div class="empty-state-text">Start a conversation</div>
                    <div class="empty-state-hint">{hint_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            # Render message history (last 20)
            render_chat_messages(st.session_state.conversation_history, max_display=20)

            # Show typing indicator if processing
            if st.session_state.is_processing:
                render_typing_indicator()

            # Auto-scroll to bottom
            auto_scroll_script()

    # ISSUE 5: Render PDF modal if open - Using enhanced viewer with PyMuPDF
    try:
        # First try enhanced viewer with page extraction support
        from streamlit_app.components.pdf_page_viewer import render_enhanced_pdf_modal

        render_enhanced_pdf_modal()
    except ImportError:
        try:
            from components.pdf_page_viewer import render_enhanced_pdf_modal

            render_enhanced_pdf_modal()
        except ImportError:
            # Fallback to basic viewer
            try:
                from streamlit_app.components.pdf_viewer_modal import (
                    render_pdf_viewer_modal,
                )

                render_pdf_viewer_modal()
            except ImportError:
                try:
                    from components.pdf_viewer_modal import render_pdf_viewer_modal

                    render_pdf_viewer_modal()
                except Exception:
                    pass  # PDF viewer not available

    # Spacer to prevent input overlap
    st.markdown("<div style='height: 120px;'></div>", unsafe_allow_html=True)

    # Sticky input at bottom (outside container for fixed positioning)
    # Update placeholder based on query_type
    if st.session_state.query_type == "pid":
        placeholder = "Ask about P&ID diagrams, tags, equipment... (Enter to send)"
    else:
        placeholder = "Ask about technical documents, manuals, specs... (Enter to send)"

    # ISSUE 2 & 3: Pass request_in_flight instead of is_processing
    user_query = render_sticky_input(
        api_base_url=api_base_url,
        request_in_flight=st.session_state.request_in_flight,
        placeholder=placeholder,
    )

    # Handle user input
    if user_query:
        # ISSUE 3 FIX: Check debounce and set request lock
        import time

        current_ts = time.time()

        # Debounce: Ignore if last submit was < 0.3 seconds ago
        if current_ts - st.session_state.last_submit_ts < 0.3:
            st.warning("⚠️ Please wait before sending another message.")
            return

        # Check if request already in flight
        if st.session_state.request_in_flight:
            st.warning("⏳ Please wait for the current request to complete.")
            return

        # Update timestamp and set lock
        st.session_state.last_submit_ts = current_ts
        st.session_state.request_in_flight = True

        # Add user message to history immediately
        st.session_state.conversation_history.append(
            {
                "role": "user",
                "content": user_query,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Set processing state (legacy compatibility)
        st.session_state.is_processing = True
        st.rerun()

    # Process query if in processing state
    if st.session_state.is_processing and st.session_state.request_in_flight:
        # Get last user message
        user_messages = [
            msg
            for msg in st.session_state.conversation_history
            if msg["role"] == "user"
        ]
        if user_messages:
            last_user_msg = user_messages[-1]["content"]

            # ISSUE 3 FIX: Use try/finally to ensure lock is always released
            try:
                response = call_api(
                    query=last_user_msg,
                    api_base_url=api_base_url,
                    conversation_id=st.session_state.conversation_id,
                    query_type=st.session_state.query_type,
                )

                if response.get("success"):
                    data = response["data"]

                    # Update conversation_id
                    st.session_state.conversation_id = data.get("conversation_id")

                    # Add bot response to history
                    st.session_state.conversation_history.append(
                        {
                            "role": "assistant",
                            "content": data.get("answer", ""),
                            "citations": data.get("citations", []),
                            "metadata": {
                                "model": data.get("meta", {}).get("model", ""),
                                "confidence": data.get("confidence", 0),
                            },
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                else:
                    # Show error
                    st.error(f"❌ Error: {response.get('error', 'Unknown error')}")

            except Exception as e:
                st.error(f"❌ Failed to get response: {str(e)}")

            finally:
                # ISSUE 3: Always release lock in finally block
                st.session_state.request_in_flight = False
                st.session_state.is_processing = False
                st.rerun()


def call_api(
    query: str,
    api_base_url: str,
    conversation_id: Optional[str] = None,
    query_type: str = "technical_doc",
) -> Dict[str, Any]:
    """
    Call the RAG API.

    Args:
        query: User query
        api_base_url: API base URL
        conversation_id: Optional conversation ID
        query_type: Query type ("technical_doc" or "pid")

    Returns:
        Response dict with success flag and data
    """
    endpoint = f"{api_base_url.rstrip('/')}/ask"

    payload = {
        "query": query,
        "language": "vi",
        "max_context": 8,
        "enable_vision_generation": True,
        "query_type": query_type,
    }

    if conversation_id:
        payload["conversation_id"] = conversation_id

    try:
        # INCREASE TIMEOUT: Changed from 30s to 120s for long RAG processing
        response = requests.post(endpoint, json=payload, timeout=120)

        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False,
                "error": f"API returned {response.status_code}",
            }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout (30s)"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to API"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def render_new_chat_button():
    """Render New Chat button in sidebar or as FAB"""
    if st.button("🔄 New Conversation", use_container_width=True, type="secondary"):
        st.session_state.conversation_id = None
        st.session_state.conversation_history = []
        st.session_state.message_offset = 0
        st.success("✓ New conversation started")
        st.rerun()
