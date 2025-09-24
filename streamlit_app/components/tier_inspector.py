"""
Tier Inspector Component - A/B testing for LLM tiers
"""

import plotly.graph_objects as go
import streamlit as st


def render():
    """Render tier inspector component"""
    st.header("⚡ Tier Inspector")
    st.caption("Compare performance and quality between light and heavy LLM tiers")

    # Query input
    st.subheader("Test Query")
    query = st.text_area(
        "Query for A/B Testing",
        placeholder="Enter a query to test with both tiers...",
        height=80,
        help="This query will be run with both light and heavy tiers for comparison",
    )

    # Test configuration
    col1, col2, col3 = st.columns(3)

    with col1:
        test_mode = st.selectbox(
            "Test Mode",
            ["Side-by-side", "Sequential", "Blind Test"],
            help="How to display the results",
        )

    with col2:
        include_embeddings = st.checkbox(
            "Include Embeddings",
            value=st.session_state.get("enable_embedding_view", False),
            disabled=not st.session_state.get("enable_embedding_view", False),
        )

    with col3:
        num_runs = st.number_input(
            "Runs per Tier",
            min_value=1,
            max_value=5,
            value=1,
            help="Multiple runs for statistical comparison",
        )

    # Run comparison button
    if st.button("🔬 Run Comparison", type="primary", use_container_width=True):
        if query:
            with st.spinner("Running A/B test..."):
                # TODO: Implement in Phase 5
                st.success(
                    "Comparison complete! (Phase 5 will implement actual A/B testing)"
                )
        else:
            st.warning("Please enter a query to test")

    # Results display
    st.divider()
    st.subheader("Comparison Results")

    # Side-by-side comparison
    light_col, heavy_col = st.columns(2)

    with light_col:
        st.markdown("### 🪶 Light Tier")
        with st.container():
            # Placeholder metrics
            st.metric("Model", "gpt-4o-mini / gemini-1.5-flash")
            st.metric("Latency", "850ms")
            st.metric("Tokens", "~500")
            st.metric("Cost", "$0.002")
            st.metric("Confidence", "0.78")

            # Answer preview
            with st.expander("Answer Preview"):
                st.info("Light tier answer will appear here")

            # Citations
            with st.expander("Citations (2)"):
                st.caption("• [Doc1] Page 12")
                st.caption("• [Doc2] Page 5")

    with heavy_col:
        st.markdown("### 🏋️ Heavy Tier")
        with st.container():
            # Placeholder metrics
            st.metric("Model", "gpt-4o / gemini-1.5-pro")
            st.metric("Latency", "2,100ms")
            st.metric("Tokens", "~1,200")
            st.metric("Cost", "$0.015")
            st.metric("Confidence", "0.92")

            # Answer preview
            with st.expander("Answer Preview"):
                st.info("Heavy tier answer will appear here")

            # Citations
            with st.expander("Citations (4)"):
                st.caption("• [Doc1] Page 12")
                st.caption("• [Doc2] Page 5")
                st.caption("• [Doc3] Page 8")
                st.caption("• [Doc4] Page 15")

    # Comparison charts
    st.divider()
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Performance Comparison")

        # Latency comparison chart
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                name="Light",
                x=["Transform", "Retrieve", "Rerank", "Generate", "Total"],
                y=[50, 200, 150, 450, 850],
                marker_color="#58a6ff",
            )
        )
        fig.add_trace(
            go.Bar(
                name="Heavy",
                x=["Transform", "Retrieve", "Rerank", "Generate", "Total"],
                y=[50, 200, 150, 1700, 2100],
                marker_color="#f85149",
            )
        )
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            yaxis_title="Latency (ms)",
            barmode="group",
            plot_bgcolor="#0d1117",
            paper_bgcolor="#0d1117",
            font=dict(color="#c9d1d9"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with chart_col2:
        st.subheader("Quality Metrics")

        # Quality comparison radar chart
        categories = [
            "Confidence",
            "Citations",
            "Completeness",
            "Accuracy",
            "Coherence",
        ]

        fig = go.Figure()
        fig.add_trace(
            go.Scatterpolar(
                r=[0.78, 0.5, 0.7, 0.75, 0.8],
                theta=categories,
                fill="toself",
                name="Light Tier",
                line_color="#58a6ff",
            )
        )
        fig.add_trace(
            go.Scatterpolar(
                r=[0.92, 0.8, 0.9, 0.95, 0.95],
                theta=categories,
                fill="toself",
                name="Heavy Tier",
                line_color="#f85149",
            )
        )
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1]), bgcolor="#0d1117"),
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor="#0d1117",
            paper_bgcolor="#0d1117",
            font=dict(color="#c9d1d9"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Embedding visualization (if enabled)
    if st.session_state.get("enable_embedding_view", False):
        st.divider()
        st.subheader("Embedding Visualization")
        st.info("🎨 PCA/UMAP visualization will be implemented in Phase 5")

        # Placeholder for embedding viz
        with st.expander("Embedding Space Preview"):
            st.caption("• Query embedding projection")
            st.caption("• Top-20 document embeddings")
            st.caption("• Cosine similarity distances")

    # Diff view
    st.divider()
    st.subheader("Answer Diff")

    diff_option = st.radio(
        "Diff View", ["Side-by-side", "Unified", "Word-level"], horizontal=True
    )

    st.info("📝 Answer difference visualization will be implemented in Phase 5")

    # Recommendation
    st.divider()
    st.subheader("Recommendation")

    with st.container():
        st.markdown(
            """
        ### 💡 Based on this comparison:

        **For this query type:**
        - ✅ **Use Light Tier** if: Speed is critical, cost-sensitive, simple factual queries
        - ✅ **Use Heavy Tier** if: Accuracy is paramount, complex reasoning, critical information

        **Observed Trade-offs:**
        - Light tier is **2.5x faster** and **7.5x cheaper**
        - Heavy tier has **18% higher confidence** and **2x more citations**

        **Suggested Configuration:**
        ```python
        execution_mode = "production"  # Auto-select based on confidence
        confidence_threshold = 0.85    # Switch to heavy if below
        ```
        """
        )

    # History
    st.divider()
    st.subheader("Comparison History")
    st.info("📊 Previous A/B test results will be stored here (Phase 5)")
