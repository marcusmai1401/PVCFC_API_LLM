"""
Dashboard Component - Overview and quick stats
"""

import random
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render():
    """Render dashboard component"""
    st.header("📊 Dashboard")
    st.caption("System overview and recent activity")

    # Quick stats row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Index Status",
            "Ready" if st.session_state.get("index_ready", True) else "Loading",
            delta=None,
            delta_color="normal",
        )

    with col2:
        # Display appropriate metric based on retriever type
        retriever_type = st.session_state.get("retriever_type", "faiss")
        if retriever_type == "weaviate":
            st.metric("Vector DB", "Weaviate", delta=None)
        else:
            st.metric("BM25 Docs", st.session_state.get("bm25_docs", "0"), delta=None)

    with col3:
        retriever_type = st.session_state.get("retriever_type", "faiss")
        if retriever_type == "weaviate":
            weaviate_status = st.session_state.get("weaviate_ready", False)
            st.metric(
                "Status", "✅ Ready" if weaviate_status else "⚠️ Not Ready", delta=None
            )
        else:
            st.metric(
                "Vector Index", st.session_state.get("faiss_vectors", "0"), delta=None
            )

    with col4:
        avg_latency = st.session_state.get("avg_latency", 0)
        st.metric(
            "Avg Latency", f"{avg_latency:.0f}ms" if avg_latency else "N/A", delta=None
        )

    with col5:
        cache_hit_rate = st.session_state.get("cache_hit_rate", 0)
        st.metric(
            "Cache Hit Rate",
            f"{cache_hit_rate:.1%}" if cache_hit_rate else "N/A",
            delta=None,
        )

    # Main content columns
    main_col1, main_col2 = st.columns([2, 1])

    with main_col1:
        # Recent requests chart
        st.subheader("Request Latency Trend")

        # Generate sample data for now
        if st.session_state.request_history:
            # Use actual request history
            df = pd.DataFrame(st.session_state.request_history)
            if "latency_ms" in df.columns:
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df["latency_ms"],
                        mode="lines+markers",
                        name="Total Latency",
                        line=dict(color="#58a6ff", width=2),
                    )
                )

                # Add breakdown if available
                if "retrieve_ms" in df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df["retrieve_ms"],
                            mode="lines",
                            name="Retrieval",
                            line=dict(color="#3fb950", width=1),
                        )
                    )

                if "generate_ms" in df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df["generate_ms"],
                            mode="lines",
                            name="Generation",
                            line=dict(color="#f85149", width=1),
                        )
                    )

                fig.update_layout(
                    height=300,
                    margin=dict(l=0, r=0, t=0, b=0),
                    xaxis_title="Request #",
                    yaxis_title="Latency (ms)",
                    hovermode="x unified",
                    plot_bgcolor="#0d1117",
                    paper_bgcolor="#0d1117",
                    font=dict(color="#c9d1d9"),
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            # Placeholder chart
            st.info("No requests yet. Use Query Lab to start testing.")

    with main_col2:
        # System health
        st.subheader("System Health")

        # Build health indicators based on retriever type
        retriever_type = st.session_state.get("retriever_type", "faiss")

        health_indicators = {
            "API Connection": "🟢 Healthy",
            "LLM Provider": "🟢 Ready"
            if st.session_state.get("llm_ready", False)
            else "🟡 Unknown",
            "Cache": "🟢 Active"
            if st.session_state.get("cache_active", False)
            else "🟡 Unknown",
        }

        # Add retriever-specific indicators
        if retriever_type == "weaviate":
            health_indicators["Weaviate DB"] = (
                "🟢 Connected"
                if st.session_state.get("weaviate_ready", False)
                else "🔴 Disconnected"
            )
        else:
            health_indicators["BM25 Index"] = (
                "🟢 Loaded"
                if st.session_state.get("bm25_ready", False)
                else "🔴 Not Loaded"
            )
            health_indicators["Vector Index"] = (
                "🟢 Loaded"
                if st.session_state.get("faiss_ready", False)
                else "🔴 Not Loaded"
            )

        for component, status in health_indicators.items():
            st.write(f"{component}: {status}")

        st.divider()

        # Recent errors
        st.subheader("Recent Issues")
        recent_errors = st.session_state.get("recent_errors", [])
        if recent_errors:
            for error in recent_errors[-3:]:  # Show last 3
                st.error(f"• {error}", icon="⚠️")
        else:
            st.success("No recent issues", icon="✅")

    # Request history table
    st.divider()
    st.subheader("Recent Requests")

    if st.session_state.request_history:
        # Convert to dataframe
        df = pd.DataFrame(st.session_state.request_history)

        # Select and format columns
        display_columns = []
        if "timestamp" in df.columns:
            display_columns.append("timestamp")
        if "query" in df.columns:
            display_columns.append("query")
        if "latency_ms" in df.columns:
            display_columns.append("latency_ms")
        if "confidence" in df.columns:
            display_columns.append("confidence")
        if "citations_count" in df.columns:
            display_columns.append("citations_count")
        if "status" in df.columns:
            display_columns.append("status")

        if display_columns:
            st.dataframe(
                df[display_columns].tail(10),  # Last 10 requests
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("No requests in current session")

    # Quick actions
    st.divider()
    st.subheader("Quick Actions")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔍 New Query", use_container_width=True):
            st.info("Switch to Query Lab tab")

    with col2:
        if st.button("📄 Generate Report", use_container_width=True):
            st.info("Switch to Report Lab tab")

    with col3:
        if st.button("📥 Ingest Data", use_container_width=True):
            st.info("Switch to Ingest tab")

    with col4:
        if st.button("📊 View Metrics", use_container_width=True):
            st.info("Switch to Metrics/Logs tab")
