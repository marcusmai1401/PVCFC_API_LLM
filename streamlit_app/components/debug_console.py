"""
Debug Console Component - Real-time log viewer with filtering

Displays recent UI events and API interactions for debugging
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

# Add parent directory to path for imports
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from app.utils.ui_logger import EventSeverity, EventType, get_logger


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to readable format"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm
    except:
        return timestamp_str


def get_severity_color(severity_name: str) -> str:
    """Get color for severity level"""
    colors = {
        "DEBUG": "#6c757d",
        "INFO": "#28a745",
        "WARNING": "#ffc107",
        "ERROR": "#dc3545",
        "CRITICAL": "#721c24",
    }
    return colors.get(severity_name, "#000000")


def get_event_icon(event_type: str) -> str:
    """Get icon for event type"""
    icons = {
        "user_input": "✏️",
        "button_click": "🔘",
        "state_change": "🔄",
        "api_request": "📤",
        "api_response": "📥",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "debug": "🐛",
        "performance": "⏱️",
        "system": "⚙️",
    }
    return icons.get(event_type, "📝")


def render_event_card(event: Dict[str, Any]):
    """Render a single event as a card"""
    col1, col2, col3 = st.columns([1, 3, 6])

    with col1:
        # Time and icon
        st.markdown(
            f"""
        <div style="text-align: center;">
            <span style="font-size: 20px;">{get_event_icon(event.get('event_type', ''))}</span><br>
            <code style="font-size: 10px;">{format_timestamp(event.get('timestamp', ''))}</code>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        # Event type and severity
        severity_name = event.get("severity_name", "INFO")
        severity_color = get_severity_color(severity_name)

        st.markdown(
            f"""
        <span style="color: {severity_color}; font-weight: bold;">
            {severity_name}
        </span><br>
        <span style="font-size: 12px; color: #666;">
            {event.get('event_type', '').replace('_', ' ').title()}
        </span>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        # Message and data
        message = event.get("message", "")
        st.markdown(f"**{message}**")

        # Show data if available
        data = event.get("data", {})
        if data:
            # Format data for display
            if isinstance(data, dict):
                # Show important fields first
                important_fields = []
                for key in [
                    "query",
                    "error_message",
                    "status_code",
                    "duration_seconds",
                    "field",
                    "button",
                ]:
                    if key in data:
                        value = data[key]
                        if isinstance(value, str) and len(value) > 100:
                            value = value[:100] + "..."
                        important_fields.append(f"`{key}`: {value}")

                if important_fields:
                    st.caption(" | ".join(important_fields[:3]))

                # Expandable full data
                with st.expander("View Full Data", expanded=False):
                    st.json(data)
            else:
                st.caption(str(data)[:200])


def render():
    """Render the debug console component"""
    st.subheader("🐛 Debug Console")
    st.caption("Real-time event log for debugging UI interactions")

    # Get logger instance
    logger = get_logger()

    # Console controls
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        # Event count selector
        event_count = st.selectbox(
            "Show last",
            options=[10, 25, 50, 100, 200],
            index=1,
            key="debug_console_event_count",
        )

    with col2:
        # Event type filter
        event_type_filter = st.selectbox(
            "Event Type",
            options=["All"] + [e.value for e in EventType],
            index=0,
            key="debug_console_event_type",
        )

    with col3:
        # Severity filter
        severity_filter = st.selectbox(
            "Minimum Severity",
            options=["All", "DEBUG", "INFO", "WARNING", "ERROR"],
            index=0,
            key="debug_console_severity",
        )

    with col4:
        # Auto-refresh toggle
        auto_refresh = st.checkbox(
            "Auto-refresh", value=False, key="debug_console_auto_refresh"
        )

    # Action buttons
    col_a1, col_a2, col_a3, col_a4 = st.columns([2, 2, 2, 2])

    with col_a1:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()

    with col_a2:
        if st.button("📊 Show Stats", use_container_width=True):
            stats = logger.get_session_stats()
            st.session_state.show_debug_stats = True

    with col_a3:
        if st.button("💾 Export Logs", use_container_width=True):
            export_file = logger.export_session_logs()
            st.success(f"Logs exported to: {export_file}")

    with col_a4:
        if st.button("🗑️ Clear Console", use_container_width=True):
            # This only clears the display, not the actual logs
            st.session_state.debug_console_cleared = True
            st.rerun()

    # Show stats if requested
    if st.session_state.get("show_debug_stats", False):
        with st.expander("📊 Session Statistics", expanded=True):
            stats = logger.get_session_stats()

            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            with col_s1:
                st.metric("Session ID", stats["session_id"][:12] + "...")
            with col_s2:
                st.metric("Total Events", stats["total_events"])
            with col_s3:
                st.metric("Errors", stats["error_count"])
            with col_s4:
                st.metric("Warnings", stats["warning_count"])

            # Event type breakdown
            if stats["event_counts_by_type"]:
                st.markdown("**Event Type Breakdown:**")
                df_stats = pd.DataFrame(
                    stats["event_counts_by_type"].items(),
                    columns=["Event Type", "Count"],
                ).sort_values("Count", ascending=False)
                st.dataframe(df_stats, use_container_width=True, hide_index=True)

            if st.button("Close Stats"):
                st.session_state.show_debug_stats = False
                st.rerun()

    # Get and filter events
    if not st.session_state.get("debug_console_cleared", False):
        # Get events based on filters
        if event_type_filter != "All":
            try:
                event_type_enum = EventType(event_type_filter)
                events = logger.get_recent_events(
                    count=event_count, event_type=event_type_enum
                )
            except:
                events = logger.get_recent_events(count=event_count)
        else:
            events = logger.get_recent_events(count=event_count)

        # Apply severity filter
        if severity_filter != "All":
            severity_levels = {
                "DEBUG": 10,
                "INFO": 20,
                "WARNING": 30,
                "ERROR": 40,
                "CRITICAL": 50,
            }
            min_severity = severity_levels.get(severity_filter, 0)
            events = [e for e in events if e.get("severity", 0) >= min_severity]

        # Display events
        if events:
            st.markdown(f"**Showing {len(events)} events**")

            # Create tabs for different view modes
            tab1, tab2, tab3 = st.tabs(["📋 List View", "📊 Table View", "📜 Raw JSON"])

            with tab1:
                # List view with cards
                for i, event in enumerate(reversed(events[-event_count:])):
                    with st.container():
                        render_event_card(event)
                        if i < len(events) - 1:
                            st.divider()

            with tab2:
                # Table view
                if events:
                    df_events = pd.DataFrame(events)

                    # Select and reorder columns
                    display_columns = []
                    for col in ["timestamp", "event_type", "severity_name", "message"]:
                        if col in df_events.columns:
                            display_columns.append(col)

                    if display_columns:
                        df_display = df_events[display_columns].copy()

                        # Format timestamp
                        if "timestamp" in df_display.columns:
                            df_display["timestamp"] = df_display["timestamp"].apply(
                                format_timestamp
                            )

                        # Truncate message
                        if "message" in df_display.columns:
                            df_display["message"] = df_display["message"].apply(
                                lambda x: x[:100] + "..." if len(x) > 100 else x
                            )

                        st.dataframe(
                            df_display,
                            use_container_width=True,
                            hide_index=True,
                            height=400,
                        )
                    else:
                        st.info("No displayable columns found")

            with tab3:
                # Raw JSON view
                st.json(events[-event_count:])
        else:
            st.info(
                "No events to display. Start interacting with the UI to see events here."
            )
    else:
        st.info("Console cleared. Click Refresh to see new events.")
        # Reset the cleared flag
        if st.button("Show Events"):
            st.session_state.debug_console_cleared = False
            st.rerun()

    # Auto-refresh logic
    if auto_refresh:
        st.caption("🔄 Auto-refresh is enabled (refreshes every 2 seconds)")
        import time

        time.sleep(2)
        st.rerun()

    # Search functionality
    with st.expander("🔍 Search Logs", expanded=False):
        search_query = st.text_input(
            "Search in messages and data",
            placeholder="Enter search term...",
            key="debug_console_search",
        )

        if search_query:
            # Filter events by search query
            all_events = logger.get_recent_events()
            matched_events = []

            for event in all_events:
                # Search in message
                if search_query.lower() in event.get("message", "").lower():
                    matched_events.append(event)
                    continue

                # Search in data (as JSON string)
                data_str = json.dumps(event.get("data", {})).lower()
                if search_query.lower() in data_str:
                    matched_events.append(event)

            st.markdown(
                f"Found **{len(matched_events)}** events matching '{search_query}'"
            )

            if matched_events:
                for event in matched_events[:10]:  # Show max 10 results
                    with st.container():
                        render_event_card(event)
                        st.divider()

                if len(matched_events) > 10:
                    st.caption(f"... and {len(matched_events) - 10} more results")
            else:
                st.info("No events found matching your search query")


def render_mini():
    """Render a mini version of the debug console for embedding"""
    logger = get_logger()

    # Get last 5 events
    events = logger.get_recent_events(count=5)

    if events:
        for event in reversed(events):
            severity_color = get_severity_color(event.get("severity_name", "INFO"))
            icon = get_event_icon(event.get("event_type", ""))

            st.markdown(
                f"""
            <div style="padding: 5px; margin: 2px 0; border-left: 3px solid {severity_color}; background-color: rgba(0,0,0,0.02);">
                <span>{icon}</span>
                <code style="font-size: 10px;">{format_timestamp(event.get('timestamp', ''))}</code>
                <span style="font-size: 12px; margin-left: 10px;">{event.get('message', '')[:50]}</span>
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("No events yet...")
