"""
Query Lab Component - Main interface for testing RAG queries
Phase 1: Full implementation with API integration and result visualization
Phase 2: Enhanced with comprehensive event logging
"""

import json
import os
import sys
import time
import traceback
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
from app.utils.ui_logger import (
    EventSeverity,
    EventType,
    get_logger,
    log_streamlit_widget,
)


def call_ask_api(
    query: str, api_base_url: str, params: Dict[str, Any], logger=None
) -> Dict[str, Any]:
    """Call the /ask API endpoint with logging"""
    if logger is None:
        logger = get_logger()

    try:
        url = f"{api_base_url}/ask"
        payload = {
            "query": query,
            "hyde": params.get("hyde", True),
            "max_context": params.get("max_context", 8),
            "language": params.get("language", "vi"),
            "execution_mode": params.get("execution_mode", "production"),
        }

        # Log API request
        logger.log_api_request(endpoint="/ask", method="POST", payload=payload)

        start_time = time.time()
        response = requests.post(url, json=payload, timeout=180)
        total_latency = (time.time() - start_time) * 1000  # Convert to ms

        if response.status_code == 200:
            result = response.json()
            result["total_latency_ms"] = total_latency

            # Log successful response
            logger.log_api_response(
                endpoint="/ask",
                status_code=response.status_code,
                response_data={
                    "answer_preview": result.get("answer", "")[:200],
                    "total_latency_ms": total_latency,
                },
                elapsed_time=total_latency / 1000,
            )

            return {"success": True, "data": result}
        else:
            # Log error response
            logger.log_api_response(
                endpoint="/ask",
                status_code=response.status_code,
                response_data=response.text[:500],
                elapsed_time=total_latency / 1000,
            )

            return {
                "success": False,
                "error": f"API returned {response.status_code}: {response.text}",
            }
    except requests.exceptions.ConnectionError as e:
        logger.log_error(
            "API connection failed",
            exception=e,
            context={"api_base_url": api_base_url, "endpoint": "/ask"},
        )
        return {
            "success": False,
            "error": "Cannot connect to API. Please check if the API server is running.",
        }
    except requests.exceptions.Timeout as e:
        logger.log_error(
            "API request timeout",
            exception=e,
            context={"timeout": 180, "api_base_url": api_base_url},
        )
        return {"success": False, "error": "Request timed out after 180 seconds"}
    except Exception as e:
        logger.log_error(
            "Unexpected API error",
            exception=e,
            context={"api_base_url": api_base_url, "endpoint": "/ask"},
        )
        return {"success": False, "error": f"Error calling API: {str(e)}"}


def create_timeline_chart(breakdown: Dict[str, float]) -> go.Figure:
    """Create a timeline visualization for latency breakdown"""
    stages = list(breakdown.keys())
    times = list(breakdown.values())

    # Create color scale
    colors = px.colors.sequential.Blues_r
    color_scale = [colors[i % len(colors)] for i in range(len(stages))]

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
        height=300,
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
                "Document": cit.get("doc_id", "Unknown"),
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
    """Render query lab component with full functionality and logging"""
    # Use built-in implementation (iOS/macOS minimal). Delegation disabled for consistency.
if vision_mode:
        st.header("Vision-Assisted Query Lab")
        st.caption("Query Lab with vision verification features enabled")
    else:
        st.header("Query Lab")
        st.caption("Test and debug RAG pipeline with full control over parameters")

    # Initialize logger
    logger = get_logger(verbose=st.session_state.get("enable_verbose_logging", False))

# Initialize session state
    if "query_results" not in st.session_state:
        st.session_state.query_results = None
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = os.getenv(
            "PVCFC_API_BASE_URL", "http://localhost:8000"
        )
    if "run_id" not in st.session_state:
        st.session_state.run_id = None
    if "ios_loading" not in st.session_state:
        st.session_state.ios_loading = False

    # Main layout
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Query Configuration")

        # API Base URL configuration
        with st.expander("API Configuration", expanded=False):
            old_api_url = st.session_state.get("api_base_url", "")
            st.session_state.api_base_url = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url,
                help="Base URL of the RAG API server",
                key="api_base_url_input",
            )

            # Log API URL change
            if old_api_url and old_api_url != st.session_state.api_base_url:
                logger.log_state_change(
                    "api_base_url", old_api_url, st.session_state.api_base_url
                )

            if st.button(
                "Test Connection", use_container_width=True, key="test_connection_btn"
            ):
                logger.log_button_click(
                    "test_connection", {"api_url": st.session_state.api_base_url}
                )

                try:
                    test_url = f"{st.session_state.api_base_url}/healthz"
                    logger.log_event(
                        EventType.INFO,
                        f"Testing connection to {test_url}",
                        {"url": test_url},
                    )

                    response = requests.get(test_url, timeout=5)

                    if response.status_code == 200:
                        st.success("✓ API is reachable")
                        logger.log_event(
                            EventType.INFO,
                            "API connection test successful",
                            {"status_code": response.status_code},
                        )
                    else:
                        st.error(f"API returned status {response.status_code}")
                        logger.log_event(
                            EventType.WARNING,
                            f"API connection test failed with status {response.status_code}",
                            {
                                "status_code": response.status_code,
                                "response": response.text[:200],
                            },
                        )
                except Exception as e:
                    st.error("✗ Cannot reach API")
                    logger.log_error(
                        "API connection test failed",
                        exception=e,
                        context={"url": st.session_state.api_base_url},
                    )

        # Query input
        query = st.text_area(
            "Query",
            placeholder="Enter your question here...",
            height=100,
            help="Natural language query to test",
            key="query_input",
            on_change=lambda: log_streamlit_widget(
                "text_area",
                "query_input",
                st.session_state.get("query_input", ""),
                logger,
            )
            if st.session_state.get("query_input")
            else None,
        )

        # Quick presets
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            if st.button("Cost Optimized", use_container_width=True, key="preset_cost"):
                st.session_state.preset = "cost"
                logger.log_button_click("preset_cost")
                logger.log_event(
                    EventType.INFO, "Applied cost-optimized preset", {"preset": "cost"}
                )
        with col_p2:
            if st.button(
                "Accuracy Focus", use_container_width=True, key="preset_accuracy"
            ):
                st.session_state.preset = "accuracy"
                logger.log_button_click("preset_accuracy")
                logger.log_event(
                    EventType.INFO,
                    "Applied accuracy-focused preset",
                    {"preset": "accuracy"},
                )
        with col_p3:
            if st.button("Debug Mode", use_container_width=True, key="preset_debug"):
                st.session_state.preset = "debug"
                logger.log_button_click("preset_debug")
                logger.log_event(
                    EventType.INFO, "Applied debug mode preset", {"preset": "debug"}
                )

        # Apply presets if selected
        preset = st.session_state.get("preset", None)
        if preset == "cost":
            default_execution_mode = "light_only"
            default_k_bm25 = 30
            default_k_faiss = 30
            default_top_k = 5
            default_hyde = False
        elif preset == "accuracy":
            default_execution_mode = "heavy_only"
            default_k_bm25 = 100
            default_k_faiss = 100
            default_top_k = 12
            default_hyde = True
        elif preset == "debug":
            default_execution_mode = "production"
            default_k_bm25 = 50
            default_k_faiss = 50
            default_top_k = 8
            default_hyde = True
        else:
            default_execution_mode = "production"
            default_k_bm25 = 50
            default_k_faiss = 50
            default_top_k = 8
            default_hyde = True

        # Execution mode
        execution_mode = st.selectbox(
            "Execution Mode",
            options=["production", "heavy_only", "light_only"],
            index=["production", "heavy_only", "light_only"].index(
                default_execution_mode
            ),
            help="Control which LLM tiers are used",
        )

        # HyDE settings
        with st.expander("HyDE Settings", expanded=False):
            enable_hyde = st.checkbox(
                "Enable HyDE",
                value=default_hyde,
                key="enable_hyde",
                on_change=lambda: logger.log_user_input(
                    "checkbox:enable_hyde",
                    st.session_state.get("enable_hyde", False),
                    {"setting_type": "hyde"},
                ),
            )
            hyde_count = st.number_input(
                "HyDE Queries",
                min_value=1,
                max_value=5,
                value=2,
                key="hyde_count",
                on_change=lambda: logger.log_user_input(
                    "number_input:hyde_count",
                    st.session_state.get("hyde_count", 2),
                    {"setting_type": "hyde"},
                ),
            )

        # Retrieval settings
        with st.expander("Retrieval Settings", expanded=False):
            k_bm25 = st.slider("BM25 Top-K", 10, 100, default_k_bm25)
            k_faiss = st.slider("FAISS Top-K", 10, 100, default_k_faiss)
            rrf_k = st.slider("RRF Constant", 10, 100, 60)
            expand_parent = st.checkbox("Expand Parent Context", value=True)

        # Reranker settings
        with st.expander("Reranker Settings", expanded=False):
            reranker_method = st.selectbox(
                "Reranker Method",
                options=["cross_encoder", "score_based", "llm", "hybrid"],
                index=0,
            )
            top_k_context = st.slider("Final Top-K", 1, 20, default_top_k)

        # Language
        language = st.radio("Language", ["vi", "en"], horizontal=True)

# Loading indicator (linear) when processing
        if st.session_state.get("ios_loading", False):
            st.markdown('<div class="ios-linear-loader" style="margin-bottom: 12px;"></div>', unsafe_allow_html=True)

        # Run button
        if st.button(
            "Run Query", type="primary", use_container_width=True, key="run_query_btn"
        ):
            if query:
                # Start a new run
                st.session_state.run_id = logger.start_new_run()

                logger.log_button_click(
                    "run_query",
                    {
                        "query_length": len(query),
                        "execution_mode": execution_mode,
                        "language": language,
                    },
                )

                logger.log_event(
                    EventType.INFO,
                    "Starting query execution",
                    {
                        "query": query[:200],  # Log first 200 chars
                        "run_id": st.session_state.run_id,
                        "parameters": {
                            "execution_mode": execution_mode,
                            "hyde": enable_hyde,
                            "language": language,
                            "max_context": top_k_context,
                        },
                    },
                    performance_key="query_execution",
                )

# Overlay ON
                    st.session_state.ios_loading = True
                    st.markdown("""
                    <div class=\"ios-overlay\" role=\"status\" aria-live=\"polite\">
                      <div class=\"ios-overlay-content\">
                        <div class=\"ios-spinner\" style=\"margin: 0 auto;\"></div>
                        <p class=\"ios-caption\" style=\"margin: 12px 0 0 0;\">Generating answer...</p>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Prepare parameters
                    params = {
                        "max_context": top_k_context,
                        "execution_mode": execution_mode,
                        "language": language,
                        "hyde": enable_hyde,
                    }

                    # Call API with logger
                    result = call_ask_api(
                        query, st.session_state.api_base_url, params, logger
                    )

                    if result["success"]:
                        st.session_state.query_results = result["data"]

                        # Log successful completion
                        logger.log_event(
                            EventType.INFO,
                            "Query completed successfully",
                            {
                                "run_id": st.session_state.run_id,
                                "total_latency_ms": result["data"].get(
                                    "total_latency_ms", 0
                                ),
                                "answer_length": len(result["data"].get("answer", "")),
                                "citations_count": len(
                                    result["data"].get("citations", [])
                                ),
                                "confidence": result["data"].get("confidence", 0),
                            },
                            performance_key="query_execution",
                        )

                        st.success("Query completed successfully")
                        st.session_state.ios_loading = False
                        st.rerun()
                    else:
                        # Log failure
                        logger.log_error(
                            "Query execution failed",
                            context={
                                "run_id": st.session_state.run_id,
                                "error": result["error"],
                            },
                        )

                        st.error(f"Error: {result['error']}")
                        st.session_state.query_results = None
                        st.session_state.ios_loading = False
                        st.rerun()
            else:
                logger.log_event(
                    EventType.WARNING,
                    "Query execution attempted without query text",
                    {},
                )
                st.warning("Please enter a query")

    with col2:
        st.subheader("Results")

        if st.session_state.query_results:
            results = st.session_state.query_results

            # Result tabs with actual data
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
                [
                    "Overview",
                    "Retrieval",
                    "Rerank",
                    "Generation",
                    "Citations",
                    "Vision Verify",
                    "Metrics",
                    "Raw Data",
                ]
            )

            with tab1:
                # Overview Tab
                st.markdown("### Answer")
                answer_text = results.get("answer", "")

                # Check if answer is empty or too short
                if not answer_text or len(answer_text.strip()) < 10:
                    st.warning(
                        "The system could not generate a complete answer. This may be due to:"
                    )
                    st.markdown(
                        """
                    - The question may need to be rephrased
                    - Relevant documents might not be indexed
                    - There might be a temporary processing issue

                    Please check the citations below for relevant documents, or try rephrasing your question.
                    """
                    )

                    # Show partial content if available
                    if results.get("context_used"):
                        st.info(
                            f"Found {len(results.get('context_used', []))} relevant document chunks. See Citations tab for details."
                        )
                else:
                    st.markdown(answer_text)

                # Display confidence and warnings
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    confidence = results.get("confidence", 0.0)
                    st.metric("Confidence", f"{confidence:.2%}")
                with col_m2:
                    num_citations = len(results.get("citations", []))
                    st.metric("Citations", num_citations)
                with col_m3:
                    total_latency = results.get("total_latency_ms", 0)
                    st.metric("Total Latency", f"{total_latency:.0f}ms")

                # Warnings
                warnings = results.get("warnings", [])
                if warnings:
st.warning("Warnings:")
                    for warn in warnings:
                        st.write(f"- {warn}")

            with tab2:
                # Retrieval Tab
                st.markdown("### Retrieval Results")

                # Get retrieval details from response
                retrieval_details = results.get("retrieval_details", {})
                retriever_type = retrieval_details.get(
                    "retriever_type", "faiss"
                )  # Default to FAISS for backward compat
                total_retrieved = retrieval_details.get("total_retrieved", 0)

                # Display mode indicator
st.info(
                    f"Retrieval Mode: **{retriever_type.upper()}** | Total Retrieved: **{total_retrieved}**"
                )

                if retriever_type == "weaviate":
                    # Weaviate Mode (Phase 4)
                    st.markdown("#### Weaviate Vector Search")
                    weaviate_results = retrieval_details.get("weaviate", [])

                    if weaviate_results:
                        st.write(f"Found **{len(weaviate_results)}** documents")

                        # Display top results
                        with st.expander("View Top Results", expanded=True):
                            for i, doc in enumerate(weaviate_results[:8], 1):
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    text_preview = doc.get("text", "")[:150]
                                    st.markdown(f"**{i}.** {text_preview}...")
                                    st.caption(
                                        f"📄 Doc: `{doc.get('doc_id', 'N/A')[:50]}...` | Page: {doc.get('page', 'N/A')}"
                                    )
                                with col2:
                                    score = doc.get("score", 0)
                                    st.metric("Score", f"{score:.4f}")
                                st.divider()
                    else:
                        st.warning("No results from Weaviate")

                else:
                    # FAISS Mode (Legacy)
                    meta = results.get("meta", {})
                    retrieval_info = meta.get("retrieval", {})

                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1:
                        st.markdown("**BM25 Results**")
                        bm25_results = retrieval_details.get(
                            "bm25", []
                        ) or retrieval_info.get("bm25_results", [])
                        st.write(f"Found {len(bm25_results)} documents")
                        if bm25_results:
                            for i, doc in enumerate(bm25_results[:5], 1):
                                st.caption(f"{i}. Score: {doc.get('score', 0):.3f}")

                    with col_r2:
                        st.markdown("**FAISS Results**")
                        faiss_results = retrieval_details.get(
                            "faiss", []
                        ) or retrieval_info.get("faiss_results", [])
                        st.write(f"Found {len(faiss_results)} documents")
                        if faiss_results:
                            for i, doc in enumerate(faiss_results[:5], 1):
                                st.caption(f"{i}. Score: {doc.get('score', 0):.3f}")

                    with col_r3:
                        st.markdown("**Total Retrieved**")
                        st.write(f"Documents {total_retrieved}")
                        from_cache = retrieval_details.get("from_cache", False)
                        if from_cache:
                            st.caption("✅ From cache")

            with tab3:
                # Rerank Tab
st.markdown("### Reranking Details")

                rerank_info = meta.get("rerank", {})

                col_rr1, col_rr2 = st.columns(2)
                with col_rr1:
                    st.markdown("**Before Reranking**")
                    before = rerank_info.get("before", [])
                    st.write(f"Input: {len(before)} documents")
                    if before:
                        df_before = pd.DataFrame(before[:10])
                        if not df_before.empty:
                            st.dataframe(
                                df_before[["doc_id", "score"]]
                                if "doc_id" in df_before.columns
                                else df_before,
                                height=200,
                            )

                with col_rr2:
                    st.markdown("**After Reranking**")
                    after = rerank_info.get("after", [])
                    st.write(f"Output: {len(after)} documents")
                    method = rerank_info.get("method", "unknown")
                    st.caption(f"Method: {method}")
                    if after:
                        df_after = pd.DataFrame(after[:10])
                        if not df_after.empty:
                            st.dataframe(
                                df_after[["doc_id", "score"]]
                                if "doc_id" in df_after.columns
                                else df_after,
                                height=200,
                            )

            with tab4:
                # Generation Tab
st.markdown("### Generation Details")

                gen_info = meta.get("generation", {})

                col_g1, col_g2, col_g3, col_g4 = st.columns(4)
                with col_g1:
                    model = gen_info.get("model", "Unknown")
                    st.metric("Model", model)
                with col_g2:
                    latency = gen_info.get("latency_ms", 0)
                    st.metric("Latency", f"{latency:.0f}ms")
                with col_g3:
                    tokens = gen_info.get("total_tokens", 0)
                    st.metric("Total Tokens", tokens)
                with col_g4:
                    cost = gen_info.get("estimated_cost", 0)
                    st.metric("Est. Cost", f"${cost:.4f}")

                # Prompt snapshot (redacted)
                st.markdown("**Prompt Structure**")
                prompt_info = gen_info.get("prompt_info", {})
                st.json(prompt_info)

            with tab5:
                # Citations Tab
                st.markdown("### 📌 Citations")

                citations = results.get("citations", [])
                if citations:
                    df_citations = format_citations(citations)
                    st.dataframe(
                        df_citations, use_container_width=True, hide_index=True
                    )

                    st.info(
                        "💡 Click on citations to open PDF viewer (coming in Phase 2)"
                    )
                else:
                    st.info("No citations found")

            with tab6:
                # Vision Verify Tab - Check if vision was actually used in generation
                generation_details = results.get("generation_details", {})
                vision_enabled = generation_details.get("vision_enabled", False)
                vision_meta = meta.get("vision_generation", {})

                if vision_meta or vision_enabled:
                    st.markdown("### 👁️ Vision Generation Used")

                    # Show vision generation metadata
                    if vision_meta:
                        col_v1, col_v2, col_v3 = st.columns(3)
                        with col_v1:
                            pages_used = len(vision_meta.get("pages_used", []))
                            st.metric("PDF Pages Used", pages_used)
                        with col_v2:
                            pages_failed = len(vision_meta.get("pages_failed", []))
                            st.metric("Pages Failed", pages_failed)
                        with col_v3:
                            success_rate = (
                                (pages_used / (pages_used + pages_failed) * 100)
                                if (pages_used + pages_failed) > 0
                                else 0
                            )
                            st.metric("Success Rate", f"{success_rate:.1f}%")

                        # Show page details
                        pages_info = vision_meta.get("pages_used", [])
                        if pages_info:
                            st.markdown("**PDF Pages Processed:**")
                            for page_info in pages_info:
                                page_num = page_info.get("page", "N/A")
                                doc_id = page_info.get("doc_id", "Unknown")
                                st.write(f"- Page {page_num} from {doc_id[:50]}...")
                    else:
                        st.info(
                            "✅ Vision generation was enabled but no detailed metadata available"
                        )
                else:
                    # Check if vision is enabled in settings
                    if st.session_state.get("enable_vision", False):
                        st.info(
                            "👁️ Vision is enabled in settings, but was not used for this query.\n"
                            "This could mean the answer was generated from text only."
                        )
                    else:
                        st.warning(
                            "Vision features are disabled. Enable 'Vision Features' in sidebar settings to use vision generation."
                        )

            with tab7:
                # Metrics Tab
                st.markdown("### 📈 Performance Metrics")

                # Latency breakdown
                breakdown = meta.get("breakdown", {})
                if breakdown:
                    fig = create_timeline_chart(breakdown)
                    st.plotly_chart(fig, use_container_width=True)

                # Additional metrics
                col_mt1, col_mt2, col_mt3 = st.columns(3)
                with col_mt1:
                    cache_hits = meta.get("cache_hits", 0)
                    st.metric("Cache Hits", cache_hits)
                with col_mt2:
                    index_size = meta.get("index_size", 0)
                    st.metric("Index Size", f"{index_size:,}")
                with col_mt3:
                    request_id = meta.get("request_id", "N/A")
                    st.metric("Request ID", request_id)

            with tab8:
                # Raw Data Tab
                st.markdown("### 📜 Raw Response Data")
                st.json(results)

        else:
            # No results yet - show placeholders
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
                [
                    "Overview",
                    "Retrieval",
                    "Rerank",
                    "Generation",
                    "Citations",
                    "Vision Verify",
                    "Metrics",
                    "Logs",
                ]
            )

            with tab1:
st.info("Answer will appear here after running a query")
                st.caption(
                    "This tab will show the final answer, confidence score, and warnings"
                )

            with tab2:
st.info("Retrieval results will be shown here")
                st.caption("BM25, FAISS, and RRF fused results")

            with tab3:
st.info("Reranking details will be displayed here")
                st.caption("Before/after scores and reranker explanation")

            with tab4:
st.info("Generation details will appear here")
                st.caption("Model info, prompt snapshot, timing")

            with tab5:
st.info("Citations will be listed here")
                st.caption("Click citations to open PDF viewer (Phase 2)")

            with tab6:
                if st.session_state.get("enable_vision", False):
st.info(
                        "Vision generation info will show here after running a query"
                    )
                    st.caption("PDF pages used, success rate, and page details")
                else:
                    st.warning(
                        "Vision features disabled. Enable 'Vision Features' in sidebar."
                    )

            with tab7:
st.info("Performance metrics will be displayed here")
                st.caption("Latency breakdown, token usage, cache hits")

            with tab8:
st.info("Request logs will stream here")
                st.caption("Structured logs filtered by trace_id")

    # Timeline visualization
    if st.session_state.query_results:
        st.divider()
        st.subheader("Pipeline Timeline")

        results = st.session_state.query_results
        meta = results.get("meta", {})
        breakdown = meta.get("breakdown", {})

        if breakdown:
            # Create timeline visualization
            total_time = sum(breakdown.values())
            st.write(f"**Total Processing Time: {total_time:.0f}ms**")

            # Create a horizontal bar for each stage
            for stage, time_ms in breakdown.items():
                percentage = (time_ms / total_time * 100) if total_time > 0 else 0
                st.progress(percentage / 100)
                st.caption(f"{stage}: {time_ms:.0f}ms ({percentage:.1f}%)")
        else:
            st.info("No timing data available for this query")
    else:
        st.divider()
        st.subheader("Pipeline Timeline")
st.info(
            "Latency breakdown timeline will be visualized here after running a query"
        )
