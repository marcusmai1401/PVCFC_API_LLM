"""
📊 Enhanced Evaluation Results Viewer

Displays real evaluation results from the batch evaluation pipeline.
Integrates with existing evaluation outputs and provides comprehensive analysis.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class EvaluationResultsViewer:
    """Enhanced evaluation results viewer with real data integration."""

    def __init__(self):
        """Initialize the evaluation results viewer."""
        self.results_dir = project_root / "results" / "evaluation"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def show_main_interface(self):
        """Display the main evaluation results interface."""
        st.title("📊 Evaluation Results Viewer")

        st.markdown(
            """
        Comprehensive analysis of your RAG pipeline's evaluation results with real data integration.
        """
        )

        # Check for available results
        available_results = self._get_available_results()

        if not available_results:
            self._show_no_results_message()
            return

        # Result selection
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_result = st.selectbox(
                "Select evaluation result:",
                available_results,
                format_func=lambda x: f"{x.stem} ({x.stat().st_mtime:.0f})",
            )

        with col2:
            if st.button("🔄 Refresh Results"):
                st.rerun()

        # Load selected result
        if selected_result:
            evaluation_data = self._load_evaluation_result(selected_result)

            if evaluation_data:
                # Display tabs
                tabs = st.tabs(
                    [
                        "📈 Overview",
                        "🔍 Detailed Metrics",
                        "📋 Individual Results",
                        "📊 Visualizations",
                        "⚖️ Comparison",
                        "💾 Export",
                    ]
                )

                with tabs[0]:
                    self._show_overview(evaluation_data)

                with tabs[1]:
                    self._show_detailed_metrics(evaluation_data)

                with tabs[2]:
                    self._show_individual_results(evaluation_data)

                with tabs[3]:
                    self._show_visualizations(evaluation_data)

                with tabs[4]:
                    self._show_comparison_interface(evaluation_data)

                with tabs[5]:
                    self._show_export_interface(evaluation_data)

    def _get_available_results(self) -> List[Path]:
        """Get list of available evaluation result files."""
        json_files = list(self.results_dir.glob("*.json"))
        jsonl_files = list(self.results_dir.glob("*.jsonl"))
        return sorted(
            json_files + jsonl_files, key=lambda x: x.stat().st_mtime, reverse=True
        )

    def _load_evaluation_result(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load evaluation result from file."""
        try:
            if file_path.suffix == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            elif file_path.suffix == ".jsonl":
                results = []
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            results.append(json.loads(line))
                return {"results": results}
            return None
        except Exception as e:
            st.error(f"Error loading results: {e}")
            return None

    def _show_no_results_message(self):
        """Show message when no results are available."""
        st.info("📊 No evaluation results found.")

        with st.expander("🚀 How to Run Evaluation"):
            st.markdown(
                """
            ### Running Batch Evaluation

            1. **Prepare QA Dataset:**
            ```python
            # Create evaluation dataset in JSONL format
            # Each line should contain:
            {
                "qa_id": "unique_id",
                "query": "Your question here",
                "intent": "definition|explanation|comparison|etc",
                "expected_behavior": "What the system should do",
                "doc_category": "technical|business|etc"
            }
            ```

            2. **Run Evaluation Script:**
            ```bash
            python -m app.evaluation.batch_runner \\
                --qa-file data/evaluation/qa_dataset.jsonl \\
                --output-dir results/evaluation \\
                --run-retrieval \\
                --run-e2e
            ```

            3. **View Results:**
            - Results will appear here automatically
            - HTML reports generated in output directory
            """
            )

    def _show_overview(self, data: Dict[str, Any]):
        """Show evaluation overview."""
        st.markdown("### 📈 Evaluation Overview")

        # Extract metrics
        metrics = data.get("metrics", {})
        overall = metrics.get("overall", {})
        retrieval = metrics.get("retrieval", {})
        e2e = metrics.get("e2e", {})
        latency = metrics.get("latency", {})

        # Summary cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Questions", overall.get("total_questions", 0))

        with col2:
            success_rate = overall.get("success_rate", 0)
            st.metric("Success Rate", f"{success_rate:.1%}")

        with col3:
            avg_latency = latency.get("avg_total_latency_ms", 0)
            st.metric("Avg Response Time", f"{avg_latency:.0f}ms")

        with col4:
            recall = retrieval.get("avg_recall_at_5", 0)
            st.metric("Recall@5", f"{recall:.3f}")

        # Performance summary
        st.markdown("---")
        st.markdown("#### 🎯 Key Performance Indicators")

        col1, col2 = st.columns(2)

        with col1:
            # Retrieval metrics
            st.markdown("**🔍 Retrieval Performance**")
            retrieval_df = pd.DataFrame(
                {
                    "Metric": ["Recall@5", "Recall@10", "Precision@5", "MRR@5"],
                    "Value": [
                        f"{retrieval.get('avg_recall_at_5', 0):.3f}",
                        f"{retrieval.get('avg_recall_at_10', 0):.3f}",
                        f"{retrieval.get('avg_precision_at_5', 0):.3f}",
                        f"{retrieval.get('avg_mrr_at_5', 0):.3f}",
                    ],
                }
            )
            st.dataframe(retrieval_df, hide_index=True, use_container_width=True)

        with col2:
            # E2E metrics
            st.markdown("**📝 End-to-End Performance**")
            e2e_df = pd.DataFrame(
                {
                    "Metric": [
                        "Citation Rate",
                        "Answer Quality",
                        "CoVe Score",
                        "Behavior Compliance",
                    ],
                    "Value": [
                        f"{e2e.get('avg_citation_rate', 0):.3f}",
                        f"{e2e.get('avg_answer_quality', 0):.3f}",
                        f"{e2e.get('avg_cove_score', 0):.3f}",
                        f"{metrics.get('behavior_validation', {}).get('behavior_compliance_rate', 0):.1%}",
                    ],
                }
            )
            st.dataframe(e2e_df, hide_index=True, use_container_width=True)

        # Latency breakdown
        st.markdown("---")
        st.markdown("#### ⚡ Latency Analysis")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Average", f"{latency.get('avg_total_latency_ms', 0):.0f}ms")

        with col2:
            st.metric("P95", f"{latency.get('p95_total_latency_ms', 0):.0f}ms")

        with col3:
            st.metric("P99", f"{latency.get('p99_total_latency_ms', 0):.0f}ms")

        # Latency distribution chart
        if "results" in data:
            latencies = [r.get("total_latency_ms", 0) for r in data["results"]]
            fig = px.histogram(
                x=latencies,
                nbins=30,
                title="Response Time Distribution",
                labels={"x": "Latency (ms)", "y": "Count"},
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    def _show_detailed_metrics(self, data: Dict[str, Any]):
        """Show detailed metrics breakdown."""
        st.markdown("### 🔍 Detailed Metrics Analysis")

        metrics = data.get("metrics", {})

        # Breakdown by intent
        intent_breakdown = metrics.get("breakdown_by_intent", {})
        if intent_breakdown:
            st.markdown("#### 📋 Performance by Intent")

            intent_data = []
            for intent, values in intent_breakdown.items():
                intent_data.append(
                    {
                        "Intent": intent,
                        "Count": values.get("count", 0),
                        "Citation Rate": f"{values.get('citation_rate', 0):.3f}",
                        "Avg Latency": f"{values.get('avg_latency_ms', 0):.0f}ms",
                        "Compliance": f"{values.get('behavior_compliance_rate', 0):.1%}",
                    }
                )

            intent_df = pd.DataFrame(intent_data)
            st.dataframe(intent_df, hide_index=True, use_container_width=True)

            # Visualization
            col1, col2 = st.columns(2)

            with col1:
                fig = px.bar(
                    intent_df,
                    x="Intent",
                    y="Count",
                    title="Query Distribution by Intent",
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.bar(
                    intent_df,
                    x="Intent",
                    y=[float(x.replace("ms", "")) for x in intent_df["Avg Latency"]],
                    title="Average Latency by Intent",
                )
                fig.update_yaxis(title="Latency (ms)")
                st.plotly_chart(fig, use_container_width=True)

        # Breakdown by document category
        doc_breakdown = metrics.get("breakdown_by_doc_category", {})
        if doc_breakdown:
            st.markdown("---")
            st.markdown("#### 🏷️ Performance by Document Category")

            doc_data = []
            for category, values in doc_breakdown.items():
                doc_data.append(
                    {
                        "Category": category,
                        "Count": values.get("count", 0),
                        "Citation Rate": f"{values.get('citation_rate', 0):.3f}",
                        "Avg Latency": f"{values.get('avg_latency_ms', 0):.0f}ms",
                        "Compliance": f"{values.get('behavior_compliance_rate', 0):.1%}",
                    }
                )

            doc_df = pd.DataFrame(doc_data)
            st.dataframe(doc_df, hide_index=True, use_container_width=True)

        # Error analysis
        error_analysis = metrics.get("error_analysis", {})
        if error_analysis:
            st.markdown("---")
            st.markdown("#### 🚨 Error Analysis")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Errors", error_analysis.get("total_errors", 0))

            with col2:
                st.metric("Error Rate", f"{error_analysis.get('error_rate', 0):.1%}")

            with col3:
                st.metric("Most Common", error_analysis.get("most_common_error", "N/A"))

    def _show_individual_results(self, data: Dict[str, Any]):
        """Show individual query results."""
        st.markdown("### 📋 Individual Query Results")

        results = data.get("results", [])

        if not results:
            st.info("No individual results available.")
            return

        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            search_term = st.text_input(
                "🔍 Search queries", placeholder="Enter search term..."
            )

        with col2:
            intent_filter = st.selectbox(
                "Filter by Intent",
                ["All"] + list(set(r.get("intent", "unknown") for r in results)),
            )

        with col3:
            quality_threshold = st.slider("Min Quality Score", 0.0, 1.0, 0.0, 0.1)

        # Filter results
        filtered_results = results

        if search_term:
            filtered_results = [
                r
                for r in filtered_results
                if search_term.lower() in r.get("query", "").lower()
            ]

        if intent_filter != "All":
            filtered_results = [
                r for r in filtered_results if r.get("intent") == intent_filter
            ]

        if quality_threshold > 0:
            filtered_results = [
                r
                for r in filtered_results
                if r.get("e2e_metrics", {}).get("answer_quality", 0)
                >= quality_threshold
            ]

        st.markdown(f"**Showing {len(filtered_results)} of {len(results)} results**")

        # Results display
        for i, result in enumerate(filtered_results[:20]):  # Show first 20
            with st.expander(f"📄 {i+1}. {result.get('query', 'N/A')[:80]}..."):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f"**Query:** {result.get('query', 'N/A')}")
                    st.markdown(f"**Intent:** {result.get('intent', 'N/A')}")
                    st.markdown(
                        f"**Expected Behavior:** {result.get('expected_behavior', 'N/A')}"
                    )

                    if result.get("generated_answer"):
                        st.markdown("**Generated Answer:**")
                        st.write(result["generated_answer"])

                    if result.get("citations"):
                        st.markdown("**Citations:**")
                        for citation in result["citations"]:
                            st.write(f"- {citation}")

                with col2:
                    # Metrics
                    e2e_metrics = result.get("e2e_metrics", {})
                    retrieval_metrics = result.get("retrieval_metrics", {})

                    st.metric(
                        "Quality Score", f"{e2e_metrics.get('answer_quality', 0):.2f}"
                    )
                    st.metric(
                        "Response Time", f"{result.get('total_latency_ms', 0):.0f}ms"
                    )
                    st.metric("Citations", len(result.get("citations", [])))
                    st.metric(
                        "Recall@5", f"{retrieval_metrics.get('recall_at_5', 0):.2f}"
                    )

                    if result.get("error"):
                        st.error(f"Error: {result['error']}")
                    else:
                        st.success("✅ Success")

    def _show_visualizations(self, data: Dict[str, Any]):
        """Show advanced visualizations."""
        st.markdown("### 📊 Advanced Visualizations")

        metrics = data.get("metrics", {})
        results = data.get("results", [])

        if not results:
            st.info("No data available for visualization.")
            return

        # Performance heatmap
        st.markdown("#### 🗺️ Performance Heatmap")

        # Prepare data for heatmap
        intent_categories = {}
        for r in results:
            intent = r.get("intent", "unknown")
            category = r.get("doc_category", "unknown")
            key = (intent, category)

            if key not in intent_categories:
                intent_categories[key] = {
                    "count": 0,
                    "total_quality": 0,
                    "total_latency": 0,
                }

            intent_categories[key]["count"] += 1
            intent_categories[key]["total_quality"] += r.get("e2e_metrics", {}).get(
                "answer_quality", 0
            )
            intent_categories[key]["total_latency"] += r.get("total_latency_ms", 0)

        # Create heatmap data
        intents = list(set(k[0] for k in intent_categories.keys()))
        categories = list(set(k[1] for k in intent_categories.keys()))

        quality_matrix = []
        for intent in intents:
            row = []
            for category in categories:
                key = (intent, category)
                if key in intent_categories and intent_categories[key]["count"] > 0:
                    avg_quality = (
                        intent_categories[key]["total_quality"]
                        / intent_categories[key]["count"]
                    )
                    row.append(avg_quality)
                else:
                    row.append(0)
            quality_matrix.append(row)

        fig = px.imshow(
            quality_matrix,
            labels=dict(x="Document Category", y="Intent", color="Avg Quality"),
            x=categories,
            y=intents,
            color_continuous_scale="RdYlGn",
            title="Average Quality Score Heatmap",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Performance over time (if timestamps available)
        st.markdown("---")
        st.markdown("#### 📈 Performance Trends")

        # Scatter plot: Latency vs Quality
        latencies = [r.get("total_latency_ms", 0) for r in results]
        qualities = [r.get("e2e_metrics", {}).get("answer_quality", 0) for r in results]
        intents = [r.get("intent", "unknown") for r in results]

        fig = px.scatter(
            x=latencies,
            y=qualities,
            color=intents,
            title="Latency vs Quality Trade-off",
            labels={"x": "Response Time (ms)", "y": "Quality Score"},
            hover_data={"Intent": intents},
        )
        st.plotly_chart(fig, use_container_width=True)

        # Parallel coordinates plot for multi-dimensional analysis
        st.markdown("---")
        st.markdown("#### 🕸️ Multi-dimensional Analysis")

        # Prepare data for parallel coordinates
        plot_data = []
        for r in results[:100]:  # Limit to 100 for performance
            plot_data.append(
                {
                    "Recall@5": r.get("retrieval_metrics", {}).get("recall_at_5", 0),
                    "Precision@5": r.get("retrieval_metrics", {}).get(
                        "precision_at_5", 0
                    ),
                    "Quality": r.get("e2e_metrics", {}).get("answer_quality", 0),
                    "Latency": min(r.get("total_latency_ms", 0) / 5000, 1),  # Normalize
                    "Citations": min(len(r.get("citations", [])) / 10, 1),  # Normalize
                    "Intent": r.get("intent", "unknown"),
                }
            )

        df_parallel = pd.DataFrame(plot_data)

        dimensions = [
            dict(label="Recall@5", values=df_parallel["Recall@5"]),
            dict(label="Precision@5", values=df_parallel["Precision@5"]),
            dict(label="Quality", values=df_parallel["Quality"]),
            dict(label="Latency (norm)", values=df_parallel["Latency"]),
            dict(label="Citations (norm)", values=df_parallel["Citations"]),
        ]

        fig = go.Figure(
            data=go.Parcoords(
                dimensions=dimensions,
                line=dict(
                    color=pd.Categorical(df_parallel["Intent"]).codes,
                    colorscale="Viridis",
                    showscale=True,
                ),
            )
        )

        fig.update_layout(title="Multi-dimensional Performance Analysis", height=400)

        st.plotly_chart(fig, use_container_width=True)

    def _show_comparison_interface(self, current_data: Dict[str, Any]):
        """Show comparison interface."""
        st.markdown("### ⚖️ Evaluation Comparison")

        st.markdown(
            """
        Compare current evaluation with another run to track improvements.
        """
        )

        # File upload for comparison
        comparison_file = st.file_uploader(
            "Upload comparison evaluation result",
            type=["json", "jsonl"],
            key="comparison_upload",
        )

        if comparison_file:
            try:
                # Load comparison data
                if comparison_file.name.endswith(".json"):
                    comparison_data = json.loads(comparison_file.read())
                else:
                    lines = comparison_file.read().decode("utf-8").strip().split("\n")
                    comparison_data = {
                        "results": [json.loads(line) for line in lines if line]
                    }

                # Extract metrics for comparison
                current_metrics = current_data.get("metrics", {})
                comparison_metrics = comparison_data.get("metrics", {})

                # Display comparison
                st.markdown("#### 📊 Metrics Comparison")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("**Metric**")

                with col2:
                    st.markdown("**Current**")

                with col3:
                    st.markdown("**Comparison**")

                # Compare key metrics
                metrics_to_compare = [
                    ("Success Rate", "overall.success_rate", "{:.1%}"),
                    ("Recall@5", "retrieval.avg_recall_at_5", "{:.3f}"),
                    ("Precision@5", "retrieval.avg_precision_at_5", "{:.3f}"),
                    ("Citation Rate", "e2e.avg_citation_rate", "{:.3f}"),
                    ("Avg Latency", "latency.avg_total_latency_ms", "{:.0f}ms"),
                    ("P95 Latency", "latency.p95_total_latency_ms", "{:.0f}ms"),
                ]

                comparison_results = []
                for label, path, fmt in metrics_to_compare:
                    keys = path.split(".")
                    current_val = current_metrics
                    comparison_val = comparison_metrics

                    for key in keys:
                        current_val = (
                            current_val.get(key, {})
                            if isinstance(current_val, dict)
                            else 0
                        )
                        comparison_val = (
                            comparison_val.get(key, {})
                            if isinstance(comparison_val, dict)
                            else 0
                        )

                    comparison_results.append(
                        {
                            "Metric": label,
                            "Current": fmt.format(current_val)
                            if "ms" not in fmt
                            else fmt.format(current_val).replace(
                                "{:.0f}", str(int(current_val))
                            ),
                            "Comparison": fmt.format(comparison_val)
                            if "ms" not in fmt
                            else fmt.format(comparison_val).replace(
                                "{:.0f}", str(int(comparison_val))
                            ),
                            "Delta": self._calculate_delta(
                                current_val, comparison_val, fmt
                            ),
                        }
                    )

                comparison_df = pd.DataFrame(comparison_results)
                st.dataframe(comparison_df, hide_index=True, use_container_width=True)

                # Visualization
                st.markdown("---")
                st.markdown("#### 📈 Visual Comparison")

                # Bar chart comparison
                metrics_for_chart = []
                for label, path, _ in metrics_to_compare[:4]:  # First 4 metrics
                    keys = path.split(".")
                    current_val = current_metrics
                    comparison_val = comparison_metrics

                    for key in keys:
                        current_val = (
                            current_val.get(key, {})
                            if isinstance(current_val, dict)
                            else 0
                        )
                        comparison_val = (
                            comparison_val.get(key, {})
                            if isinstance(comparison_val, dict)
                            else 0
                        )

                    metrics_for_chart.append(
                        {
                            "Metric": label,
                            "Current": float(current_val),
                            "Comparison": float(comparison_val),
                        }
                    )

                chart_df = pd.DataFrame(metrics_for_chart)

                fig = go.Figure()
                fig.add_trace(
                    go.Bar(name="Current", x=chart_df["Metric"], y=chart_df["Current"])
                )
                fig.add_trace(
                    go.Bar(
                        name="Comparison",
                        x=chart_df["Metric"],
                        y=chart_df["Comparison"],
                    )
                )

                fig.update_layout(
                    title="Key Metrics Comparison", barmode="group", yaxis_title="Value"
                )

                st.plotly_chart(fig, use_container_width=True)

            except Exception as e:
                st.error(f"Error loading comparison file: {e}")

    def _show_export_interface(self, data: Dict[str, Any]):
        """Show export interface."""
        st.markdown("### 💾 Export Results")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📄 Export as JSON"):
                json_str = json.dumps(data, indent=2, ensure_ascii=False)
                st.download_button(
                    label="⬇️ Download JSON",
                    data=json_str,
                    file_name=f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                )

        with col2:
            if st.button("📊 Export Metrics as CSV"):
                metrics_df = self._metrics_to_dataframe(data.get("metrics", {}))
                csv = metrics_df.to_csv(index=False)
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name=f"evaluation_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )

        with col3:
            if st.button("📝 Export Summary Report"):
                summary = self._generate_summary_report(data)
                st.download_button(
                    label="⬇️ Download Report",
                    data=summary,
                    file_name=f"evaluation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                )

    def _calculate_delta(self, current: float, comparison: float, fmt: str) -> str:
        """Calculate and format delta between values."""
        if comparison == 0:
            return "N/A"

        if "%" in fmt:
            delta = (current - comparison) * 100
            return f"{delta:+.1f}%"
        else:
            delta = current - comparison
            if "ms" in fmt:
                return f"{delta:+.0f}ms"
            else:
                return f"{delta:+.3f}"

    def _metrics_to_dataframe(self, metrics: Dict[str, Any]) -> pd.DataFrame:
        """Convert metrics dictionary to DataFrame."""
        rows = []

        def flatten_dict(d, parent_key=""):
            for k, v in d.items():
                new_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    flatten_dict(v, new_key)
                else:
                    rows.append({"Metric": new_key, "Value": v})

        flatten_dict(metrics)
        return pd.DataFrame(rows)

    def _generate_summary_report(self, data: Dict[str, Any]) -> str:
        """Generate markdown summary report."""
        metrics = data.get("metrics", {})

        report = f"""# RAG Evaluation Summary Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overall Performance

- **Total Questions**: {metrics.get('overall', {}).get('total_questions', 0)}
- **Success Rate**: {metrics.get('overall', {}).get('success_rate', 0):.1%}
- **Average Latency**: {metrics.get('latency', {}).get('avg_total_latency_ms', 0):.0f}ms

## Retrieval Performance

- **Recall@5**: {metrics.get('retrieval', {}).get('avg_recall_at_5', 0):.3f}
- **Recall@10**: {metrics.get('retrieval', {}).get('avg_recall_at_10', 0):.3f}
- **Precision@5**: {metrics.get('retrieval', {}).get('avg_precision_at_5', 0):.3f}
- **MRR@5**: {metrics.get('retrieval', {}).get('avg_mrr_at_5', 0):.3f}

## End-to-End Performance

- **Citation Rate**: {metrics.get('e2e', {}).get('avg_citation_rate', 0):.3f}
- **Answer Quality**: {metrics.get('e2e', {}).get('avg_answer_quality', 0):.3f}
- **CoVe Score**: {metrics.get('e2e', {}).get('avg_cove_score', 0):.3f}

## Latency Analysis

- **Average**: {metrics.get('latency', {}).get('avg_total_latency_ms', 0):.0f}ms
- **P95**: {metrics.get('latency', {}).get('p95_total_latency_ms', 0):.0f}ms
- **P99**: {metrics.get('latency', {}).get('p99_total_latency_ms', 0):.0f}ms

## Recommendations

Based on the evaluation results:
1. Monitor queries with high latency (P99: {metrics.get('latency', {}).get('p99_total_latency_ms', 0):.0f}ms)
2. Investigate intents with low citation rates
3. Review failed queries for pattern analysis
"""

        return report


def show_evaluation_results():
    """Main entry point for evaluation results viewer."""
    viewer = EvaluationResultsViewer()
    viewer.show_main_interface()
