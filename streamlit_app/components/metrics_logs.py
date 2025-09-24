"""
Metrics & Logs Component - System monitoring and debugging
"""

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render():
    """Render metrics and logs component"""
    st.header("📈 Metrics & Logs")
    st.caption("System performance monitoring and request debugging")

    # Tab layout
    metrics_tab, logs_tab, traces_tab, prometheus_tab = st.tabs(
        ["Metrics", "Logs", "Traces", "Prometheus"]
    )

    with metrics_tab:
        render_metrics_tab()

    with logs_tab:
        render_logs_tab()

    with traces_tab:
        render_traces_tab()

    with prometheus_tab:
        render_prometheus_tab()


def render_metrics_tab():
    """Render metrics dashboard"""
    st.subheader("System Metrics")

    # Time range selector
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        time_range = st.selectbox(
            "Time Range", ["Last 15m", "Last 1h", "Last 6h", "Last 24h", "Last 7d"]
        )

    with col2:
        refresh_rate = st.selectbox("Auto Refresh", ["Off", "5s", "10s", "30s", "60s"])

    with col3:
        if st.button("🔄 Refresh Now"):
            st.rerun()

    # Key metrics row
    st.divider()
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Request Rate", "12.5 req/min", delta="+2.3", delta_color="normal")

    with metric_col2:
        st.metric("P95 Latency", "2,350ms", delta="+150ms", delta_color="inverse")

    with metric_col3:
        st.metric("Error Rate", "0.8%", delta="-0.2%", delta_color="normal")

    with metric_col4:
        st.metric("Cache Hit Rate", "68.5%", delta="+5.2%", delta_color="normal")

    # Charts
    st.divider()
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Request Latency Distribution")

        # Latency histogram
        fig = go.Figure()
        fig.add_trace(
            go.Histogram(
                x=[
                    450,
                    600,
                    750,
                    850,
                    950,
                    1100,
                    1250,
                    1400,
                    1600,
                    1800,
                    2000,
                    2200,
                    2500,
                    2800,
                    3200,
                    3500,
                    4000,
                    4500,
                    5000,
                ],
                nbinsx=20,
                name="Latency",
                marker_color="#58a6ff",
            )
        )
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis_title="Latency (ms)",
            yaxis_title="Count",
            plot_bgcolor="#0d1117",
            paper_bgcolor="#0d1117",
            font=dict(color="#c9d1d9"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with chart_col2:
        st.subheader("Pipeline Step Breakdown")

        # Step breakdown pie chart
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=["Transform", "Retrieve", "Rerank", "Generate", "CoVe"],
                    values=[5, 25, 15, 45, 10],
                    hole=0.3,
                    marker_colors=[
                        "#58a6ff",
                        "#3fb950",
                        "#f85149",
                        "#a371f7",
                        "#f0883e",
                    ],
                )
            ]
        )
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor="#0d1117",
            paper_bgcolor="#0d1117",
            font=dict(color="#c9d1d9"),
            showlegend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Token usage
    st.divider()
    st.subheader("Token Usage")

    token_col1, token_col2, token_col3 = st.columns(3)

    with token_col1:
        st.metric("Total Tokens Today", "125.4K")
        st.caption("Prompt: 85.2K | Completion: 40.2K")

    with token_col2:
        st.metric("Avg per Request", "856")
        st.caption("Light: 425 | Heavy: 1,287")

    with token_col3:
        st.metric("Estimated Cost", "$2.45")
        st.caption("Light: $0.35 | Heavy: $2.10")

    # Error breakdown
    st.divider()
    st.subheader("Error Analysis")

    error_data = {
        "Error Type": ["Timeout", "Rate Limit", "Model Error", "Index Error", "Other"],
        "Count": [3, 1, 2, 0, 1],
        "Percentage": ["42.9%", "14.3%", "28.6%", "0%", "14.3%"],
    }

    df = pd.DataFrame(error_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_logs_tab():
    """Render logs viewer"""
    st.subheader("Request Logs")

    # Log filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        log_level = st.selectbox(
            "Log Level", ["All", "DEBUG", "INFO", "WARNING", "ERROR"]
        )

    with col2:
        trace_filter = st.text_input("Trace ID", placeholder="Filter by trace...")

    with col3:
        endpoint_filter = st.selectbox(
            "Endpoint", ["All", "/ask", "/locate", "/report", "/ingest"]
        )

    with col4:
        if st.button("Apply Filters"):
            st.info("Filters applied (Phase 1 will implement)")

    # Log viewer
    st.divider()

    # Sample logs
    log_entries = [
        {
            "timestamp": "2025-09-16 10:30:45.123",
            "level": "INFO",
            "trace_id": "abc123def456",
            "message": "Request started: /ask",
            "endpoint": "/ask",
            "latency_ms": None,
        },
        {
            "timestamp": "2025-09-16 10:30:45.234",
            "level": "DEBUG",
            "trace_id": "abc123def456",
            "message": "Query transformed with HyDE: 2 variants",
            "endpoint": "/ask",
            "latency_ms": 112,
        },
        {
            "timestamp": "2025-09-16 10:30:45.567",
            "level": "INFO",
            "trace_id": "abc123def456",
            "message": "Retrieved 50 BM25 + 50 FAISS results",
            "endpoint": "/ask",
            "latency_ms": 333,
        },
        {
            "timestamp": "2025-09-16 10:30:46.789",
            "level": "INFO",
            "trace_id": "abc123def456",
            "message": "Request completed: /ask [200]",
            "endpoint": "/ask",
            "latency_ms": 1666,
        },
        {
            "timestamp": "2025-09-16 10:31:12.456",
            "level": "ERROR",
            "trace_id": "xyz789ghi012",
            "message": "Rate limit exceeded for client",
            "endpoint": "/ask",
            "latency_ms": None,
        },
    ]

    # Display logs
    for entry in log_entries:
        level_color = {"DEBUG": "🔵", "INFO": "🟢", "WARNING": "🟡", "ERROR": "🔴"}.get(
            entry["level"], "⚪"
        )

        with st.expander(
            f"{level_color} [{entry['timestamp']}] {entry['message'][:50]}..."
        ):
            st.json(entry)

    # Tail logs option
    st.divider()
    if st.checkbox("📜 Tail Logs (Live)"):
        st.info("Live log streaming will be implemented in Phase 1")


def render_traces_tab():
    """Render distributed traces"""
    st.subheader("Request Traces")

    # Trace search
    col1, col2 = st.columns([3, 1])
    with col1:
        trace_id_input = st.text_input(
            "Trace ID", placeholder="Enter trace ID to view details..."
        )

    with col2:
        if st.button("Search", use_container_width=True):
            if trace_id_input:
                st.info(f"Loading trace: {trace_id_input}")

    # Recent traces
    st.divider()
    st.write("**Recent Traces**")

    traces_data = {
        "Trace ID": ["abc123...", "xyz789...", "def456..."],
        "Timestamp": ["10:30:45", "10:31:12", "10:32:03"],
        "Endpoint": ["/ask", "/ask", "/report"],
        "Duration": ["1,666ms", "429ms", "3,245ms"],
        "Status": ["✅", "❌", "✅"],
    }

    df = pd.DataFrame(traces_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Trace visualization
    st.divider()
    st.write("**Trace Timeline**")

    # Waterfall chart for trace
    fig = go.Figure(
        go.Waterfall(
            name="Pipeline",
            orientation="h",
            measure=[
                "relative",
                "relative",
                "relative",
                "relative",
                "relative",
                "total",
            ],
            y=["Transform", "Retrieve", "Rerank", "Generate", "CoVe", "Total"],
            x=[50, 333, 150, 1000, 133, None],
            connector={
                "mode": "between",
                "line": {"width": 2, "color": "rgb(200, 200, 200)"},
            },
            decreasing={"marker": {"color": "#f85149"}},
            increasing={"marker": {"color": "#3fb950"}},
            totals={"marker": {"color": "#58a6ff"}},
        )
    )

    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis_title="Duration (ms)",
        plot_bgcolor="#0d1117",
        paper_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Span details
    with st.expander("Span Details"):
        st.json(
            {
                "trace_id": "abc123def456",
                "spans": [
                    {
                        "span_id": "s1",
                        "operation": "query_transform",
                        "duration_ms": 50,
                    },
                    {"span_id": "s2", "operation": "bm25_search", "duration_ms": 183},
                    {"span_id": "s3", "operation": "faiss_search", "duration_ms": 150},
                    {"span_id": "s4", "operation": "rerank", "duration_ms": 150},
                    {"span_id": "s5", "operation": "generate", "duration_ms": 1000},
                    {"span_id": "s6", "operation": "cove_verify", "duration_ms": 133},
                ],
            }
        )


def render_prometheus_tab():
    """Render Prometheus metrics"""
    st.subheader("Prometheus Metrics")

    # Scrape endpoint
    col1, col2 = st.columns([3, 1])
    with col1:
        endpoint = st.text_input(
            "Metrics Endpoint", value=f"{st.session_state.api_base_url}/metrics"
        )

    with col2:
        if st.button("Scrape", use_container_width=True):
            with st.spinner("Scraping metrics..."):
                # TODO: Actually scrape /metrics
                st.success("Metrics scraped")

    # Sample metrics display
    st.divider()
    st.write("**Sample Metrics**")

    st.code(
        """
# HELP rag_requests_total Total number of RAG requests
# TYPE rag_requests_total counter
rag_requests_total{endpoint="/ask",status="success"} 1234
rag_requests_total{endpoint="/ask",status="error"} 7
rag_requests_total{endpoint="/locate",status="success"} 456
rag_requests_total{endpoint="/report",status="success"} 89

# HELP rag_request_duration_seconds Request latency in seconds
# TYPE rag_request_duration_seconds histogram
rag_request_duration_seconds_bucket{endpoint="/ask",step="total",le="0.5"} 123
rag_request_duration_seconds_bucket{endpoint="/ask",step="total",le="1.0"} 456
rag_request_duration_seconds_bucket{endpoint="/ask",step="total",le="2.5"} 789
rag_request_duration_seconds_bucket{endpoint="/ask",step="total",le="5.0"} 1012
rag_request_duration_seconds_bucket{endpoint="/ask",step="total",le="+Inf"} 1234

# HELP rag_cache_hits_total Total cache hits
# TYPE rag_cache_hits_total counter
rag_cache_hits_total{cache_type="retrieval"} 856
rag_cache_hits_total{cache_type="rerank"} 234
rag_cache_hits_total{cache_type="transform"} 123
    """,
        language="prometheus",
    )

    # Key metrics summary
    st.divider()
    st.write("**Key Metrics Summary**")

    metrics_summary = {
        "Metric": [
            "Total Requests",
            "Success Rate",
            "P50 Latency",
            "P95 Latency",
            "Cache Hit Rate",
            "Index Size",
        ],
        "Value": ["1,779", "99.6%", "850ms", "2,350ms", "68.5%", "12,456 docs"],
    }

    df = pd.DataFrame(metrics_summary)
    st.dataframe(df, use_container_width=True, hide_index=True)
