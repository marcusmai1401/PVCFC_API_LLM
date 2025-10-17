"""
Material Design 3 Theme Utilities
Handles theme switching and CSS injection for Streamlit
"""

from pathlib import Path
from typing import Literal

import streamlit as st

ThemeMode = Literal["light", "dark", "system"]


def load_css_file(css_path: Path) -> str:
    """Load CSS file contents."""
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def inject_m3_styles():
    """Inject iOS/macOS tokens and styles into Streamlit (icons minimized)."""
    styles_dir = Path(__file__).parent.parent / "styles"

    # Load tokens and base CSS (no global icon fonts)
    tokens_css = load_css_file(styles_dir / "tokens.css")
    m3_css = load_css_file(styles_dir / "m3.css")

    # Inject into Streamlit
    st.markdown(
        f"""
        <style>
        {tokens_css}
        {m3_css}
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_system_theme() -> Literal["light", "dark"]:
    """Detect system theme preference (client-side)."""
    # Inject JS to detect system theme
    theme_js = """
    <script>
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const themeInput = window.parent.document.querySelector('input[data-testid="system-theme-detector"]');
    if (themeInput) {
        themeInput.value = prefersDark ? 'dark' : 'light';
        themeInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    </script>
    """
    st.markdown(theme_js, unsafe_allow_html=True)

    # Fallback to light if detection fails
    return "light"


def set_theme(mode: ThemeMode):
    """Set the theme mode and apply it to the document."""
    # Store in session state
    st.session_state.theme_mode = mode

    # Determine actual theme to apply
    if mode == "system":
        actual_theme = get_system_theme()
    else:
        actual_theme = mode

    # Apply theme via data attribute on root
    theme_script = f"""
    <script>
    document.documentElement.setAttribute('data-theme', '{actual_theme}');
    </script>
    """
    st.markdown(theme_script, unsafe_allow_html=True)

    return actual_theme


def render_theme_switcher():
    """Render a theme switcher widget."""
    # Initialize theme in session state
    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "system"

    # Theme selector
    col1, col2 = st.columns([3, 1])

    with col2:
        theme_options = ["light", "dark", "system"]
        theme_icons = {"light": "☀️", "dark": "🌙", "system": "💻"}

        selected_theme = st.selectbox(
            "Theme",
            options=theme_options,
            index=theme_options.index(st.session_state.theme_mode),
            format_func=lambda x: f"{theme_icons[x]} {x.title()}",
            key="theme_selector",
            label_visibility="collapsed",
        )

        # Apply theme if changed
        if selected_theme != st.session_state.theme_mode:
            set_theme(selected_theme)
            st.rerun()

    return st.session_state.theme_mode


def initialize_m3_theme():
    """Initialize M3 theme - call this once at app startup."""
    # Inject styles
    inject_m3_styles()

    # Set initial theme
    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "system"

    set_theme(st.session_state.theme_mode)


def get_current_theme() -> Literal["light", "dark"]:
    """Get the currently active theme (resolved from system if needed)."""
    mode = st.session_state.get("theme_mode", "system")

    if mode == "system":
        return get_system_theme()

    return mode
