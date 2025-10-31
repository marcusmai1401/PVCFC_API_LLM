"""
Typing indicator component for chat interface.
Shows animated dots while bot is responding.
"""

import streamlit as st


def render_typing_indicator():
    """
    Render typing indicator with animated dots.

    Shows three dots with bouncing animation to indicate
    that the bot is processing a response.
    """
    st.markdown(
        """
        <div class="message-wrapper bot">
            <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
