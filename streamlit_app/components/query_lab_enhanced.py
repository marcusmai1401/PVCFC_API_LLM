"""
Query Lab Component - Enhanced with full Phase 1 features
Includes complete API integration, global config usage, and all UI features
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Add parent directory to path for imports
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

try:
    from app.utils.ui_logger import (
        EventSeverity,
        EventType,
        get_logger,
        log_streamlit_widget,
    )
except ImportError:
    # Fallback logger if ui_logger is not available
    class MockLogger:
        def log_event(self, *args, **kwargs):
            pass

        def log_api_request(self, *args, **kwargs):
            pass

        def log_api_response(self, *args, **kwargs):
            pass

        def log_error(self, *args, **kwargs):
            pass

        def log_user_input(self, *args, **kwargs):
            pass

        def log_button_click(self, *args, **kwargs):
            pass

        def start_new_run(self):
            return "mock_run_id"

    def get_logger(**kwargs):
        return MockLogger()


def call_rag_api(
    query: str,
    api_base_url: str,
    auth_token: str,
    params: Dict[str, Any],
    timeout: int = 30,
    max_retries: int = 3,
    logger=None,
) -> Dict[str, Any]:
    """Call the RAG API endpoint with full error handling and retries"""

    if logger is None:
        logger = get_logger()

    # Prepare headers
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    # Build the endpoint URL
    endpoint = f"{api_base_url.rstrip('/')}/ask"

    # Prepare payload
    payload = {"query": query, **params}

    # Log API request
    logger.log_api_request(endpoint=endpoint, method="POST", payload=payload)

    # Retry logic
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            response = requests.post(
                endpoint, json=payload, headers=headers, timeout=timeout
            )
            elapsed_time = time.time() - start_time

            # Log API response
            logger.log_api_response(
                endpoint=endpoint,
                status_code=response.status_code,
                response_data=response.json()
                if response.status_code == 200
                else response.text[:500],
                elapsed_time=elapsed_time,
            )

            if response.status_code == 200:
                result = response.json()
                result["total_latency_ms"] = elapsed_time * 1000
                return {"success": True, "data": result}
            else:
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                    continue
                return {
                    "success": False,
                    "error": f"API returned {response.status_code}: {response.text}",
                }

        except requests.exceptions.ConnectionError as e:
            logger.log_error(
                "API connection failed",
                exception=e,
                context={"api_base_url": api_base_url, "attempt": attempt + 1},
            )
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return {
                "success": False,
                "error": f"Cannot connect to API at {api_base_url}. Please check if the server is running.",
            }

        except requests.exceptions.Timeout as e:
            logger.log_error(
                "API request timeout",
                exception=e,
                context={"timeout": timeout, "attempt": attempt + 1},
            )
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return {
                "success": False,
                "error": f"Request timed out after {timeout} seconds",
            }

        except Exception as e:
            logger.log_error(
                "Unexpected API error", exception=e, context={"attempt": attempt + 1}
            )
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    return {"success": False, "error": "Max retries exceeded"}


def create_timeline_chart(breakdown: Dict[str, float]) -> go.Figure:
    """Create a timeline visualization for latency breakdown"""
    if not breakdown:
        breakdown = {
            "Query Transform": 50,
            "Retrieval": 200,
            "Reranking": 150,
            "Generation": 800,
            "Post-processing": 30,
        }

    stages = list(breakdown.keys())
    times = list(breakdown.values())

    fig = go.Figure(
        data=[
            go.Bar(
                x=times,
                y=stages,
                orientation="h",
                marker=dict(
                    color=times,
                    colorscale="Blues",
                    showscale=True,
                    colorbar=dict(title="ms"),
                ),
                text=[f"{t:.1f}ms" for t in times],
                textposition="outside",
            )
        ]
    )

    fig.update_layout(
        title="Pipeline Latency Breakdown",
        xaxis_title="Latency (ms)",
        yaxis_title="Stage",
        height=400,
        margin=dict(l=150, r=50, t=50, b=50),
        showlegend=False,
    )

    return fig


def format_citations(citations: List[Dict]) -> pd.DataFrame:
    """Format citations for display"""
    if not citations:
        return pd.DataFrame()

    formatted = []
    for i, cit in enumerate(citations, 1):
        formatted.append(
            {
                "#": i,
                "Document": cit.get("doc_id", cit.get("document", "Unknown")),
                "Page": cit.get("page", "N/A"),
                "Score": f"{cit.get('score', 0):.3f}",
                "Has BBox": "✓" if cit.get("bbox") else "✗",
                "Text Preview": (cit.get("text", "")[:100] + "...")
                if cit.get("text")
                else "N/A",
            }
        )

    return pd.DataFrame(formatted)


def render(vision_mode=False):
    """Render the Query Lab component with full Phase 1 functionality

    Args:
        vision_mode: Whether to enable vision verification features
    """

    # Header based on mode
    if vision_mode:
        st.header("👁️ Vision-Assisted Query Lab")
        st.caption("Query Lab with vision verification features enabled")
    else:
        st.header("🔬 Query Lab")
        st.caption("Full control over RAG query parameters with live API testing")

    # Initialize logger
    logger = get_logger(verbose=st.session_state.get("enable_verbose_logging", False))

    # Get global configuration
    api_base_url = st.session_state.get("api_base_url", "http://127.0.0.1:8000")
    auth_token = st.session_state.get("auth_token", "")
    enable_vision = st.session_state.get("enable_vision", False) or vision_mode
    enable_embedding = st.session_state.get("enable_embedding", False)
    global_config = st.session_state.get("global_config", {})
    timeout = global_config.get("timeout", 30)
    max_retries = global_config.get("max_retries", 3)

    # Initialize session state for results
    if "query_results" not in st.session_state:
        st.session_state.query_results = None
    if "query_history" not in st.session_state:
        st.session_state.query_history = []

    # Main layout
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("⚙️ Query Configuration")

        # Show API endpoint status
        with st.expander("🌐 API Status", expanded=True):
            st.info(f"**Endpoint:** `{api_base_url}`")
            if auth_token:
                st.success("🔐 Authentication configured")
            else:
                st.warning("🔓 No authentication token")

            # Feature flags status
            if enable_vision or enable_embedding:
                st.markdown("**Active Features:**")
                if enable_vision:
                    st.success("✅ Vision verification enabled")
                if enable_embedding:
                    st.success("✅ Embedding visualization enabled")

        # Query Input
        st.markdown("### 📝 Query Input")
        query = st.text_area(
            "Enter your query",
            placeholder="Type or paste your question here...",
            height=120,
            key="query_input",
        )

        # Presets
        st.markdown("### 🎯 Presets")
        preset = st.selectbox(
            "Load preset configuration",
            ["Custom", "Fast", "Balanced", "Accurate", "Debug"],
            help="Quick configurations for different use cases",
        )

        # Apply preset defaults
        if preset == "Fast":
            default_params = {
                "execution_mode": "light_only",
                "max_context": 5,
                "hyde": False,
                "k_bm25": 30,
                "k_faiss": 30,
                "rerank": False,
            }
        elif preset == "Accurate":
            default_params = {
                "execution_mode": "heavy_only",
                "max_context": 12,
                "hyde": True,
                "k_bm25": 100,
                "k_faiss": 100,
                "rerank": True,
            }
        elif preset == "Debug":
            default_params = {
                "execution_mode": "production",
                "max_context": 8,
                "hyde": True,
                "k_bm25": 50,
                "k_faiss": 50,
                "rerank": True,
                "debug": True,
            }
        else:  # Balanced or Custom
            default_params = {
                "execution_mode": "production",
                "max_context": 8,
                "hyde": True,
                "k_bm25": 50,
                "k_faiss": 50,
                "rerank": True,
            }

        # Advanced Settings
        with st.expander("🔧 Advanced Settings", expanded=False):
            # Execution Mode
            execution_mode = st.selectbox(
                "Execution Mode",
                ["production", "heavy_only", "light_only"],
                index=["production", "heavy_only", "light_only"].index(
                    default_params.get("execution_mode", "production")
                ),
                help="Control which LLM tiers to use",
            )

            # HyDE Settings
            st.markdown("#### HyDE Configuration")
            enable_hyde = st.checkbox(
                "Enable HyDE",
                value=default_params.get("hyde", True),
                help="Use Hypothetical Document Embeddings",
            )

            if enable_hyde:
                hyde_queries = st.slider(
                    "Number of HyDE queries", min_value=1, max_value=5, value=2
                )

            # Retrieval Settings
            st.markdown("#### Retrieval Configuration")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                k_bm25 = st.number_input(
                    "BM25 Top-K",
                    min_value=10,
                    max_value=200,
                    value=default_params.get("k_bm25", 50),
                    step=10,
                )
            with col_r2:
                k_faiss = st.number_input(
                    "FAISS Top-K",
                    min_value=10,
                    max_value=200,
                    value=default_params.get("k_faiss", 50),
                    step=10,
                )

            # Reranking
            st.markdown("#### Reranking")
            enable_rerank = st.checkbox(
                "Enable Reranking", value=default_params.get("rerank", True)
            )

            if enable_rerank:
                rerank_method = st.selectbox(
                    "Reranking Method", ["cross_encoder", "llm", "hybrid"], index=0
                )

            # Final Context
            max_context = st.slider(
                "Max Context Documents",
                min_value=1,
                max_value=20,
                value=default_params.get("max_context", 8),
            )

            # Language
            language = st.radio(
                "Response Language", ["vi", "en"], horizontal=True, index=0
            )

        # Vision Settings (if enabled)
        if enable_vision:
            with st.expander("👁️ Vision Settings", expanded=False):
                st.markdown("#### Vision Verification")
                confidence_threshold = st.slider(
                    "Confidence Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.7,
                    step=0.05,
                )

                enable_ocr_fallback = st.checkbox(
                    "Enable OCR Fallback",
                    value=True,
                    help="Use OCR when vision model confidence is low",
                )

        # Submit Button
        submit_btn = st.button(
            "🚀 Execute Query",
            type="primary",
            use_container_width=True,
            disabled=not query,
        )

        # Clear Results Button
        if st.session_state.query_results:
            if st.button("🗑️ Clear Results", use_container_width=True):
                st.session_state.query_results = None
                st.rerun()

    # Right column - Results
    with col2:
        st.subheader("📊 Results")

        if submit_btn and query:
            # Log query submission
            run_id = logger.start_new_run()
            logger.log_button_click(
                "execute_query",
                {
                    "query_length": len(query),
                    "preset": preset,
                    "execution_mode": execution_mode,
                },
            )

            # Prepare API parameters
            api_params = {
                "execution_mode": execution_mode,
                "hyde": enable_hyde,
                "max_context": max_context,
                "language": language,
                "k_bm25": k_bm25,
                "k_faiss": k_faiss,
                "enable_rerank": enable_rerank,
            }

            if enable_vision:
                api_params["enable_vision"] = True
                api_params["vision_confidence_threshold"] = confidence_threshold
                api_params["ocr_fallback"] = enable_ocr_fallback

            # Show spinner while processing
            with st.spinner("🔄 Processing query..."):
                start_time = time.time()

                # Call API
                result = call_rag_api(
                    query=query,
                    api_base_url=api_base_url,
                    auth_token=auth_token,
                    params=api_params,
                    timeout=timeout,
                    max_retries=max_retries,
                    logger=logger,
                )

                total_time = time.time() - start_time

                if result["success"]:
                    # Store results
                    st.session_state.query_results = result["data"]

                    # Add to history
                    st.session_state.query_history.append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "query": query,
                            "params": api_params,
                            "response_time": total_time,
                            "success": True,
                        }
                    )

                    # Log success
                    logger.log_event(
                        EventType.INFO,
                        "Query completed successfully",
                        {
                            "run_id": run_id,
                            "total_time": total_time,
                            "answer_length": len(result["data"].get("answer", "")),
                            "citations_count": len(result["data"].get("citations", [])),
                        },
                    )

                    st.success(f"✅ Query completed in {total_time:.2f}s")
                    st.rerun()
                else:
                    # Log error
                    logger.log_error(
                        "Query execution failed",
                        context={"run_id": run_id, "error": result["error"]},
                    )

                    st.error(f"❌ {result['error']}")
                    st.session_state.query_results = None

        # Display results if available
        if st.session_state.query_results:
            results = st.session_state.query_results

            # Create tabs for different result views
            tabs = st.tabs(
                [
                    "📝 Answer",
                    "📚 Citations",
                    "⏱️ Timeline",
                    "🔍 Retrieval",
                    "📊 Metrics",
                    "🔬 Debug",
                    "📜 Raw",
                ]
            )

            with tabs[0]:  # Answer tab
                st.markdown("### Generated Answer")
                answer = results.get("answer", "No answer generated")
                st.markdown(answer)

                # Confidence and metrics
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    confidence = results.get("confidence", 0.0)
                    st.metric("Confidence", f"{confidence:.2%}")
                with col_m2:
                    citations_count = len(results.get("citations", []))
                    st.metric("Citations", citations_count)
                with col_m3:
                    latency = results.get("total_latency_ms", 0)
                    st.metric("Latency", f"{latency:.0f}ms")

                # Warnings if any
                warnings = results.get("warnings", [])
                if warnings:
                    st.warning("⚠️ Warnings detected")
                    for warning in warnings:
                        st.write(f"• {warning}")

            with tabs[1]:  # Citations tab
                st.markdown("### Document Citations")
                citations = results.get("citations", [])
                if citations:
                    # Format and display citations
                    df_citations = format_citations(citations)
                    st.dataframe(df_citations, use_container_width=True)

                    # Show clickable links if PDF viewer is available
                    if any(cit.get("bbox") for cit in citations):
                        st.info(
                            "💡 Citations with bounding boxes can be viewed in the PDF Viewer (Phase 2)"
                        )
                else:
                    st.info("No citations found for this query")

            with tabs[2]:  # Timeline tab
                st.markdown("### Latency Timeline")
                breakdown = results.get("latency_breakdown", {})
                if breakdown:
                    fig = create_timeline_chart(breakdown)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # Generate mock timeline for demo
                    mock_breakdown = {
                        "Query Transform": results.get("transform_time", 50),
                        "Retrieval": results.get("retrieval_time", 200),
                        "Reranking": results.get("rerank_time", 150),
                        "Generation": results.get("generation_time", 800),
                        "Post-processing": results.get("postprocess_time", 30),
                    }
                    fig = create_timeline_chart(mock_breakdown)
                    st.plotly_chart(fig, use_container_width=True)

            with tabs[3]:  # Retrieval tab
                st.markdown("### Retrieval Results")

                # BM25 Results
                st.markdown("#### BM25 Results")
                bm25_results = results.get("retrieval", {}).get("bm25", [])
                if bm25_results:
                    st.write(f"Found {len(bm25_results)} BM25 matches")
                    with st.expander("View BM25 Results"):
                        for i, doc in enumerate(bm25_results[:5], 1):
                            st.write(f"**#{i}** - Score: {doc.get('score', 0):.3f}")
                            st.write(doc.get("text", "")[:200] + "...")

                # FAISS Results
                st.markdown("#### FAISS Results")
                faiss_results = results.get("retrieval", {}).get("faiss", [])
                if faiss_results:
                    st.write(f"Found {len(faiss_results)} FAISS matches")
                    with st.expander("View FAISS Results"):
                        for i, doc in enumerate(faiss_results[:5], 1):
                            st.write(f"**#{i}** - Score: {doc.get('score', 0):.3f}")
                            st.write(doc.get("text", "")[:200] + "...")

            with tabs[4]:  # Metrics tab
                st.markdown("### Performance Metrics")

                # Create metrics grid
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### Retrieval Metrics")
                    metrics = results.get("metrics", {})
                    st.write(f"• Precision: {metrics.get('precision', 0):.2%}")
                    st.write(f"• Recall: {metrics.get('recall', 0):.2%}")
                    st.write(f"• F1 Score: {metrics.get('f1', 0):.2%}")
                    st.write(f"• MRR: {metrics.get('mrr', 0):.3f}")

                with col2:
                    st.markdown("#### Generation Metrics")
                    st.write(f"• Token Count: {metrics.get('token_count', 0)}")
                    st.write(f"• Cost: ${metrics.get('cost', 0):.4f}")
                    st.write(f"• Tokens/sec: {metrics.get('tokens_per_sec', 0):.1f}")
                    st.write(f"• Model: {results.get('model', 'Unknown')}")

            with tabs[5]:  # Debug tab
                st.markdown("### Debug Information")

                # Query transformation
                st.markdown("#### Query Transformation")
                transformed = results.get("transformed_query", query)
                if transformed != query:
                    st.write("**Original:**", query)
                    st.write("**Transformed:**", transformed)
                else:
                    st.info("Query was not transformed")

                # HyDE queries if used
                hyde_queries = results.get("hyde_queries", [])
                if hyde_queries:
                    st.markdown("#### HyDE Queries")
                    for i, hq in enumerate(hyde_queries, 1):
                        st.write(f"{i}. {hq}")

                # Debug logs
                debug_logs = results.get("debug_logs", [])
                if debug_logs:
                    st.markdown("#### Debug Logs")
                    for log in debug_logs:
                        st.code(log)

            with tabs[6]:  # Raw tab
                st.markdown("### Raw Response")
                st.json(results)

        else:
            # No results yet
            st.info(
                "👆 Configure your query parameters and click 'Execute Query' to see results"
            )

            # Show query history if available
            if st.session_state.query_history:
                st.markdown("### 📜 Recent Queries")
                for item in st.session_state.query_history[-3:]:
                    with st.expander(f"Query at {item['timestamp'][:19]}"):
                        st.write("**Query:**", item["query"][:100] + "...")
                        st.write("**Response Time:**", f"{item['response_time']:.2f}s")
                        st.write(
                            "**Status:**",
                            "✅ Success" if item["success"] else "❌ Failed",
                        )


if __name__ == "__main__":
    # For testing the component standalone
    st.set_page_config(page_title="Query Lab", layout="wide")
    render()
