"""
📊 Evaluation Results Component

Interface for viewing and analyzing batch evaluation results with interactive charts.
Displays comprehensive metrics, trends, and detailed analysis.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


def show_evaluation_results():
    """Display the evaluation results interface."""
    st.title("📊 Evaluation Results - Performance Analysis")

    st.markdown(
        """
    Analyze your RAG pipeline's performance with comprehensive metrics, interactive charts, and detailed insights.
    """
    )

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Dashboard", "🔍 Detailed Analysis", "📋 Results Browser", "⚖️ Comparison"]
    )

    with tab1:
        show_dashboard()

    with tab2:
        show_detailed_analysis()

    with tab3:
        show_results_browser()

    with tab4:
        show_comparison_interface()


def show_dashboard():
    """Show the main evaluation dashboard."""
    st.markdown("### 📈 Evaluation Dashboard")

    # Load or generate sample data
    eval_data = get_sample_evaluation_data()

    if not eval_data:
        st.info(
            "📊 No evaluation results available. Run batch evaluations to see results here."
        )

        # Show example of how to run evaluation
        with st.expander("🚀 How to Generate Evaluation Results"):
            st.code(
                """
# Example: Run batch evaluation
from app.evaluation.batch_runner import BatchEvaluationRunner, EvaluationConfig

config = EvaluationConfig(
    qa_file="data/evaluation/qa_dataset.jsonl",
    output_dir="results/evaluation",
    run_retrieval_eval=True,
    run_e2e_eval=True
)

runner = BatchEvaluationRunner(config)
results = await runner.run_evaluation()
            """,
                language="python",
            )
        return

    # Summary metrics
    st.markdown("#### 🎯 Key Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_queries = len(eval_data)
        st.metric("Total Queries Evaluated", total_queries)

    with col2:
        avg_response_time = np.mean([r["total_latency_ms"] for r in eval_data]) / 1000
        st.metric("Avg Response Time", f"{avg_response_time:.2f}s", delta="-0.15s")

    with col3:
        success_rate = np.mean(
            [1 if not r.get("has_error", False) else 0 for r in eval_data]
        )
        st.metric("Success Rate", f"{success_rate:.1%}", delta="2.3%")

    with col4:
        avg_quality = np.mean([r.get("answer_quality_score", 0.8) for r in eval_data])
        st.metric("Avg Answer Quality", f"{avg_quality:.2f}", delta="0.05")

    # Performance charts
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        # Response time distribution
        st.markdown("#### ⏱️ Response Time Distribution")
        response_times = [r["total_latency_ms"] / 1000 for r in eval_data]

        fig = px.histogram(
            x=response_times,
            nbins=20,
            title="Response Time Distribution (seconds)",
            labels={"x": "Response Time (s)", "y": "Count"},
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Quality scores by intent
        st.markdown("#### 🎯 Quality by Intent")

        # Group by intent
        intent_quality = {}
        for r in eval_data:
            intent = r.get("intent", "unknown")
            quality = r.get("answer_quality_score", 0.8)
            if intent not in intent_quality:
                intent_quality[intent] = []
            intent_quality[intent].append(quality)

        # Calculate averages
        avg_by_intent = {
            intent: np.mean(scores) for intent, scores in intent_quality.items()
        }

        fig = px.bar(
            x=list(avg_by_intent.keys()),
            y=list(avg_by_intent.values()),
            title="Average Quality Score by Intent",
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    # Detailed metrics breakdown
    st.markdown("---")
    st.markdown("#### 📊 Detailed Performance Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**🔍 Retrieval Metrics**")
        avg_recall_5 = np.mean([r.get("retrieval_recall_5", 0.85) for r in eval_data])
        avg_precision_5 = np.mean(
            [r.get("retrieval_precision_5", 0.92) for r in eval_data]
        )

        st.metric("Recall@5", f"{avg_recall_5:.2f}")
        st.metric("Precision@5", f"{avg_precision_5:.2f}")

    with col2:
        st.markdown("**📝 Generation Metrics**")
        avg_citations = np.mean([len(r.get("citations", [])) for r in eval_data])
        citation_rate = np.mean([1 if r.get("citations") else 0 for r in eval_data])

        st.metric("Avg Citations", f"{avg_citations:.1f}")
        st.metric("Citation Rate", f"{citation_rate:.1%}")

    with col3:
        st.markdown("**⚡ Performance Metrics**")
        avg_retrieval_time = np.mean(
            [r.get("retrieval_latency_ms", 450) for r in eval_data]
        )
        avg_generation_time = np.mean(
            [r.get("generation_latency_ms", 1200) for r in eval_data]
        )

        st.metric("Avg Retrieval Time", f"{avg_retrieval_time:.0f}ms")
        st.metric("Avg Generation Time", f"{avg_generation_time:.0f}ms")

    # Recent trends (if we have time-series data)
    st.markdown("---")
    st.markdown("#### 📈 Performance Trends")

    # Generate sample time series data
    dates = [datetime.now() - timedelta(days=x) for x in range(30, 0, -1)]
    quality_trend = [
        0.8 + 0.1 * np.sin(x / 5) + np.random.normal(0, 0.02) for x in range(30)
    ]
    latency_trend = [
        2.1 + 0.3 * np.sin(x / 7) + np.random.normal(0, 0.1) for x in range(30)
    ]

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Answer Quality Over Time", "Response Time Over Time"),
        vertical_spacing=0.1,
    )

    # Quality trend
    fig.add_trace(
        go.Scatter(
            x=dates, y=quality_trend, name="Quality Score", line=dict(color="blue")
        ),
        row=1,
        col=1,
    )

    # Latency trend
    fig.add_trace(
        go.Scatter(
            x=dates, y=latency_trend, name="Response Time (s)", line=dict(color="red")
        ),
        row=2,
        col=1,
    )

    fig.update_layout(height=400, showlegend=False)
    fig.update_yaxes(title_text="Quality Score", row=1, col=1)
    fig.update_yaxes(title_text="Response Time (s)", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)


def show_detailed_analysis():
    """Show detailed analysis interface."""
    st.markdown("### 🔍 Detailed Analysis")

    # Analysis filters
    col1, col2, col3 = st.columns(3)

    with col1:
        analysis_type = st.selectbox(
            "Analysis Type",
            [
                "Performance Analysis",
                "Quality Analysis",
                "Error Analysis",
                "Comparison Analysis",
            ],
        )

    with col2:
        time_range = st.selectbox(
            "Time Range", ["Last 7 days", "Last 30 days", "Last 90 days", "All time"]
        )

    with col3:
        category_filter = st.selectbox(
            "Category Filter",
            ["All Categories", "technical", "business", "general", "other"],
        )

    eval_data = get_sample_evaluation_data()

    if analysis_type == "Performance Analysis":
        show_performance_analysis(eval_data, time_range, category_filter)
    elif analysis_type == "Quality Analysis":
        show_quality_analysis(eval_data, time_range, category_filter)
    elif analysis_type == "Error Analysis":
        show_error_analysis(eval_data, time_range, category_filter)
    else:
        show_comparison_analysis(eval_data, time_range, category_filter)


def show_performance_analysis(data, time_range, category_filter):
    """Show performance analysis."""
    st.markdown("#### ⚡ Performance Analysis")

    # Latency breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🕒 Latency Breakdown**")

        avg_retrieval = np.mean([r.get("retrieval_latency_ms", 450) for r in data])
        avg_generation = np.mean([r.get("generation_latency_ms", 1200) for r in data])
        avg_other = np.mean(
            [
                r.get("total_latency_ms", 1800)
                - r.get("retrieval_latency_ms", 450)
                - r.get("generation_latency_ms", 1200)
                for r in data
            ]
        )

        latency_data = {
            "Component": ["Retrieval", "Generation", "Other"],
            "Time (ms)": [avg_retrieval, avg_generation, avg_other],
        }

        fig = px.pie(
            latency_data,
            values="Time (ms)",
            names="Component",
            title="Average Latency Breakdown",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**📊 Performance Distribution**")

        # Performance metrics
        metrics_data = []
        for r in data:
            metrics_data.append(
                {
                    "Query": r.get("qa_id", "unknown"),
                    "Total Time (s)": r.get("total_latency_ms", 1800) / 1000,
                    "Retrieval Time (ms)": r.get("retrieval_latency_ms", 450),
                    "Generation Time (ms)": r.get("generation_latency_ms", 1200),
                    "Quality Score": r.get("answer_quality_score", 0.8),
                }
            )

        df = pd.DataFrame(metrics_data)

        fig = px.scatter(
            df,
            x="Total Time (s)",
            y="Quality Score",
            size="Generation Time (ms)",
            hover_data=["Retrieval Time (ms)"],
            title="Performance vs Quality Trade-off",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Performance table
    st.markdown("**📋 Performance Summary**")

    performance_summary = pd.DataFrame(
        {
            "Metric": [
                "Average Response Time",
                "P95 Response Time",
                "P99 Response Time",
                "Fastest Response",
                "Slowest Response",
                "Queries > 5s",
                "Queries > 10s",
            ],
            "Value": [
                f"{np.mean([r['total_latency_ms'] for r in data])/1000:.2f}s",
                f"{np.percentile([r['total_latency_ms'] for r in data], 95)/1000:.2f}s",
                f"{np.percentile([r['total_latency_ms'] for r in data], 99)/1000:.2f}s",
                f"{np.min([r['total_latency_ms'] for r in data])/1000:.2f}s",
                f"{np.max([r['total_latency_ms'] for r in data])/1000:.2f}s",
                f"{sum(1 for r in data if r['total_latency_ms'] > 5000)} ({sum(1 for r in data if r['total_latency_ms'] > 5000)/len(data):.1%})",
                f"{sum(1 for r in data if r['total_latency_ms'] > 10000)} ({sum(1 for r in data if r['total_latency_ms'] > 10000)/len(data):.1%})",
            ],
        }
    )

    st.dataframe(performance_summary, use_container_width=True)


def show_quality_analysis(data, time_range, category_filter):
    """Show quality analysis."""
    st.markdown("#### 🎯 Quality Analysis")

    col1, col2 = st.columns(2)

    with col1:
        # Quality distribution
        st.markdown("**📊 Quality Score Distribution**")
        quality_scores = [r.get("answer_quality_score", 0.8) for r in data]

        fig = px.histogram(
            x=quality_scores,
            nbins=20,
            title="Quality Score Distribution",
            labels={"x": "Quality Score", "y": "Count"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Quality by category
        st.markdown("**🏷️ Quality by Category**")

        category_quality = {}
        for r in data:
            category = r.get("doc_category", "unknown")
            quality = r.get("answer_quality_score", 0.8)
            if category not in category_quality:
                category_quality[category] = []
            category_quality[category].append(quality)

        category_avg = {
            cat: np.mean(scores) for cat, scores in category_quality.items()
        }

        fig = px.bar(
            x=list(category_avg.keys()),
            y=list(category_avg.values()),
            title="Average Quality by Category",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Citation analysis
    st.markdown("**📖 Citation Analysis**")

    col1, col2, col3 = st.columns(3)

    with col1:
        citation_rate = np.mean([1 if r.get("citations") else 0 for r in data])
        st.metric("Citation Rate", f"{citation_rate:.1%}")

    with col2:
        avg_citations = np.mean([len(r.get("citations", [])) for r in data])
        st.metric("Avg Citations per Answer", f"{avg_citations:.1f}")

    with col3:
        citation_quality = np.mean([r.get("citation_rate", 0.9) for r in data])
        st.metric("Avg Citation Quality", f"{citation_quality:.2f}")


def show_error_analysis(data, time_range, category_filter):
    """Show error analysis."""
    st.markdown("#### 🚨 Error Analysis")

    # Error statistics
    error_data = [r for r in data if r.get("has_error", False)]
    total_errors = len(error_data)
    error_rate = total_errors / len(data) if data else 0

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Errors", total_errors)

    with col2:
        st.metric("Error Rate", f"{error_rate:.1%}")

    with col3:
        if error_data:
            # Most common error type (simulate)
            st.metric("Most Common Error", "Timeout")
        else:
            st.metric("Most Common Error", "None")

    if error_data:
        # Error breakdown
        st.markdown("**📊 Error Breakdown**")

        # Simulate error types
        error_types = [
            "Timeout",
            "API Error",
            "Parsing Error",
            "Retrieval Error",
            "Generation Error",
        ]
        error_counts = [5, 3, 2, 4, 1]  # Mock data

        fig = px.pie(
            values=error_counts, names=error_types, title="Error Types Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Error table
        st.markdown("**📋 Recent Errors**")
        error_df = pd.DataFrame(
            [
                {
                    "Query ID": r.get("qa_id", "unknown"),
                    "Query": r.get("query", "Unknown")[:50] + "...",
                    "Error Type": "Timeout",  # Mock
                    "Error Message": r.get("error_message", "No details available")[
                        :100
                    ]
                    + "...",
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                for r in error_data[:10]  # Show first 10 errors
            ]
        )

        st.dataframe(error_df, use_container_width=True)
    else:
        st.success("🎉 No errors found in the selected data!")


def show_comparison_analysis(data, time_range, category_filter):
    """Show comparison analysis."""
    st.markdown("#### ⚖️ Comparison Analysis")

    st.info(
        "📊 Comparison analysis helps you compare different evaluation runs, configurations, or time periods."
    )

    # Comparison options
    comparison_type = st.selectbox(
        "Comparison Type",
        ["Time Periods", "Configurations", "Model Versions", "Categories"],
    )

    if comparison_type == "Time Periods":
        show_time_period_comparison(data)
    elif comparison_type == "Configurations":
        show_configuration_comparison(data)
    else:
        st.info(f"📈 {comparison_type} comparison coming soon!")


def show_time_period_comparison(data):
    """Show time period comparison."""
    st.markdown("**📅 Time Period Comparison**")

    # Mock comparison data for different periods
    periods = ["Week 1", "Week 2", "Week 3", "Week 4"]
    metrics = {
        "Average Quality": [0.78, 0.82, 0.85, 0.87],
        "Response Time (s)": [2.1, 2.0, 1.9, 1.8],
        "Success Rate": [0.92, 0.94, 0.96, 0.97],
        "Citation Rate": [0.88, 0.90, 0.91, 0.93],
    }

    comparison_df = pd.DataFrame(metrics, index=periods)

    # Line chart showing trends
    fig = go.Figure()

    for metric in metrics.keys():
        fig.add_trace(
            go.Scatter(x=periods, y=metrics[metric], mode="lines+markers", name=metric)
        )

    fig.update_layout(
        title="Performance Trends Over Time",
        xaxis_title="Time Period",
        yaxis_title="Metric Value",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Comparison table
    st.dataframe(comparison_df)


def show_configuration_comparison(data):
    """Show configuration comparison."""
    st.markdown("**⚙️ Configuration Comparison**")

    # Mock comparison data for different configurations
    configs = ["Config A", "Config B", "Config C"]
    comparison_data = {
        "Configuration": configs,
        "Quality Score": [0.82, 0.87, 0.84],
        "Response Time (s)": [2.1, 1.8, 2.3],
        "Success Rate": [0.94, 0.97, 0.92],
        "Cost Score": [0.8, 0.6, 0.9],  # Normalized cost metric
    }

    comparison_df = pd.DataFrame(comparison_data)

    # Radar chart for multi-dimensional comparison
    fig = go.Figure()

    for i, config in enumerate(configs):
        fig.add_trace(
            go.Scatterpolar(
                r=[
                    comparison_data["Quality Score"][i],
                    1
                    - comparison_data["Response Time (s)"][i]
                    / 3,  # Normalized (inverted)
                    comparison_data["Success Rate"][i],
                    comparison_data["Cost Score"][i],
                ],
                theta=["Quality Score", "Speed", "Reliability", "Cost Efficiency"],
                fill="toself",
                name=config,
            )
        )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        showlegend=True,
        title="Configuration Comparison (Normalized)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Detailed comparison table
    st.dataframe(comparison_df)


def show_results_browser():
    """Show individual results browser."""
    st.markdown("### 📋 Results Browser")

    eval_data = get_sample_evaluation_data()

    if not eval_data:
        st.info("📋 No evaluation results to browse.")
        return

    # Search and filter
    col1, col2, col3 = st.columns(3)

    with col1:
        search_term = st.text_input(
            "🔍 Search queries", placeholder="Enter search term..."
        )

    with col2:
        intent_filter = st.selectbox(
            "Filter by Intent",
            ["All"] + list(set([r.get("intent", "unknown") for r in eval_data])),
        )

    with col3:
        quality_threshold = st.slider("Min Quality Score", 0.0, 1.0, 0.0, 0.1)

    # Filter data
    filtered_data = eval_data

    if search_term:
        filtered_data = [
            r
            for r in filtered_data
            if search_term.lower() in r.get("query", "").lower()
        ]

    if intent_filter != "All":
        filtered_data = [r for r in filtered_data if r.get("intent") == intent_filter]

    filtered_data = [
        r
        for r in filtered_data
        if r.get("answer_quality_score", 0.8) >= quality_threshold
    ]

    st.markdown(f"**Found {len(filtered_data)} results**")

    # Results list
    for i, result in enumerate(filtered_data[:10]):  # Show first 10 results
        with st.expander(f"📄 Query {i+1}: {result.get('query', 'Unknown')[:50]}..."):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Query:** {result.get('query', 'N/A')}")
                st.markdown(f"**Intent:** {result.get('intent', 'N/A')}")
                st.markdown(
                    f"**Expected Behavior:** {result.get('expected_behavior', 'N/A')}"
                )

                if result.get("generated_answer"):
                    st.markdown(f"**Generated Answer:** {result['generated_answer']}")
                else:
                    st.markdown("**Generated Answer:** *Not available*")

            with col2:
                # Metrics
                st.metric(
                    "Quality Score", f"{result.get('answer_quality_score', 0.8):.2f}"
                )
                st.metric(
                    "Response Time", f"{result.get('total_latency_ms', 1800)/1000:.2f}s"
                )
                st.metric("Citations", len(result.get("citations", [])))

                if result.get("has_error"):
                    st.error(f"Error: {result.get('error_message', 'Unknown error')}")
                else:
                    st.success("✅ Success")


def show_comparison_interface():
    """Show comparison interface."""
    st.markdown("### ⚖️ Evaluation Comparison")

    st.markdown(
        """
    Compare different evaluation runs to understand performance changes and improvements.
    """
    )

    # File upload for comparison
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📁 Baseline Evaluation")
        baseline_file = st.file_uploader(
            "Upload baseline results", type=["json", "jsonl"], key="baseline"
        )

        if baseline_file:
            st.success("✅ Baseline loaded")
        else:
            st.info("📤 Upload baseline evaluation results")

    with col2:
        st.markdown("#### 📁 Comparison Evaluation")
        comparison_file = st.file_uploader(
            "Upload comparison results", type=["json", "jsonl"], key="comparison"
        )

        if comparison_file:
            st.success("✅ Comparison loaded")
        else:
            st.info("📤 Upload comparison evaluation results")

    if baseline_file and comparison_file:
        st.markdown("---")
        st.markdown("#### 📊 Comparison Results")

        # Mock comparison metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Quality Score", "0.87", delta="0.05")

        with col2:
            st.metric("Response Time", "1.8s", delta="-0.3s")

        with col3:
            st.metric("Success Rate", "97%", delta="3%")

        with col4:
            st.metric("Citation Rate", "93%", delta="2%")

        # Detailed comparison chart
        st.markdown("#### 📈 Detailed Comparison")

        # Mock detailed comparison data
        metrics = ["Quality", "Speed", "Accuracy", "Citations", "Relevance"]
        baseline_scores = [0.82, 0.78, 0.85, 0.88, 0.80]
        comparison_scores = [0.87, 0.85, 0.88, 0.90, 0.84]

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                name="Baseline", x=metrics, y=baseline_scores, marker_color="lightblue"
            )
        )

        fig.add_trace(
            go.Bar(
                name="Comparison",
                x=metrics,
                y=comparison_scores,
                marker_color="darkblue",
            )
        )

        fig.update_layout(
            title="Performance Comparison",
            xaxis_title="Metrics",
            yaxis_title="Score",
            barmode="group",
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("📊 Upload both baseline and comparison files to see detailed analysis.")


def get_sample_evaluation_data() -> List[Dict[str, Any]]:
    """Generate sample evaluation data for demo purposes."""
    np.random.seed(42)  # For consistent demo data

    sample_data = []
    intents = ["definition", "explanation", "comparison", "how-to", "factual"]
    categories = ["technical", "business", "general"]

    for i in range(50):  # Generate 50 sample results
        result = {
            "qa_id": f"qa_{i:03d}",
            "query": f"Sample query {i+1} about RAG systems and implementation",
            "intent": np.random.choice(intents),
            "doc_category": np.random.choice(categories),
            "expected_behavior": "Should provide accurate and comprehensive answer",
            "generated_answer": f"Generated answer for query {i+1} with relevant information...",
            "citations": [
                {
                    "title": f"Document {j}",
                    "source": f"doc_{j}.pdf",
                    "relevance": 0.8 + 0.2 * np.random.random(),
                }
                for j in range(np.random.randint(1, 4))
            ],
            "answer_quality_score": 0.7 + 0.3 * np.random.random(),
            "citation_rate": 0.8 + 0.2 * np.random.random(),
            "retrieval_recall_5": 0.75 + 0.25 * np.random.random(),
            "retrieval_precision_5": 0.85 + 0.15 * np.random.random(),
            "retrieval_latency_ms": 300 + 300 * np.random.random(),
            "generation_latency_ms": 800 + 800 * np.random.random(),
            "total_latency_ms": None,  # Will be calculated
            "has_error": np.random.random() < 0.05,  # 5% error rate
            "error_message": "Request timeout" if np.random.random() < 0.05 else None,
            "cove_verification_score": 0.8 + 0.2 * np.random.random(),
        }

        # Calculate total latency
        result["total_latency_ms"] = (
            result["retrieval_latency_ms"]
            + result["generation_latency_ms"]
            + np.random.normal(200, 50)
        )

        sample_data.append(result)

    return sample_data
