"""
Query Lab Component - Improved version with enhanced citations
Phase 1 improvements:
- Show both score and confidence in citations
- Add PDF page viewer button
- Force execution_mode = production
"""

import base64
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

try:
    from app.utils.ui_logger import (
        EventSeverity,
        EventType,
        get_logger,
        log_streamlit_widget,
    )
except ImportError:
    # Fallback if logger not available
    class DummyLogger:
        def log_api_request(self, *args, **kwargs):
            pass

        def log_api_response(self, *args, **kwargs):
            pass

        def log_error(self, *args, **kwargs):
            pass

        def log_event(self, *args, **kwargs):
            pass

        def log_button_click(self, *args, **kwargs):
            pass

        def log_state_change(self, *args, **kwargs):
            pass

        def log_user_input(self, *args, **kwargs):
            pass

        def start_new_run(self):
            return "dummy-run-id"

    def get_logger(*args, **kwargs):
        return DummyLogger()


def render_pdf_page(
    api_base_url: str, pdf_path: str, page_num: int, doc_id: str, logger=None
):
    """Render a PDF page with viewer controls"""
    try:
        # Initialize logger if not provided
        if logger is None:
            logger = get_logger()

        # Log the render event
        render_start = time.time()
        logger.log_event(
            EventType.INFO,
            "PDF page render started",
            {"doc_id": doc_id, "page": page_num, "pdf_path": pdf_path[:50] + "..."},
        )

        # Create a unique key for this modal
        modal_key = f"pdf_modal_{doc_id}_{page_num}"

        # Header with document info
        st.markdown(f"### 📄 Document: {doc_id}")
        st.markdown(f"**Page {page_num}**")

        # Create buttons row for controls
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 3])

        # Build the direct URL for the PDF page with proper encoding
        from urllib.parse import urlencode

        render_url = f"{api_base_url}/api/pdf/render-page"
        params_dict = {
            "pdf_path": pdf_path,
            "page_num": str(page_num),
            "dpi": "200",
            "format": "png",
            "use_cache": "true",
        }
        params_str = urlencode(params_dict)
        full_url = f"{render_url}?{params_str}"

        with btn_col1:
            # Open in new tab button (using markdown link styled as button)
            st.markdown(
                f'<a href="{full_url}" target="_blank" style="'
                f"display: inline-block; padding: 0.25rem 0.75rem; "
                f"background-color: #0066cc; color: white; text-decoration: none; "
                f'border-radius: 0.25rem; font-size: 14px;">'
                f"🔗 Open in New Tab</a>",
                unsafe_allow_html=True,
            )

        with btn_col2:
            # Download button (optional, for future enhancement)
            if st.button(
                "💾 Download",
                key=f"download_{modal_key}",
                help="Download this page as image",
            ):
                logger.log_button_click(
                    "download_pdf_page", {"doc_id": doc_id, "page": page_num}
                )
                st.info("Download feature coming soon...")

        # Load and display the page image
        params = {
            "pdf_path": pdf_path,
            "page_num": page_num,
            "dpi": 200,  # Higher DPI for better quality
            "format": "png",
            "use_cache": True,
        }

        with st.spinner("Loading PDF page..."):
            response = requests.get(render_url, params=params, timeout=30)

            if response.status_code == 200:
                # Log successful render
                render_time = (time.time() - render_start) * 1000
                logger.log_event(
                    EventType.INFO,
                    "PDF page rendered successfully",
                    {
                        "doc_id": doc_id,
                        "page": page_num,
                        "render_time_ms": round(render_time, 2),
                        "image_size_bytes": len(response.content),
                    },
                )

                # Display the image
                st.image(
                    response.content,
                    caption=f"Page {page_num} from {doc_id}",
                    use_column_width=True,
                )

                # Get metadata from headers
                total_pages = response.headers.get("X-Total-Pages", "Unknown")
                width = response.headers.get("X-Image-Width", "Unknown")
                height = response.headers.get("X-Image-Height", "Unknown")

                # Show page info
                info_col1, info_col2, info_col3 = st.columns(3)
                with info_col1:
                    st.info(f"📄 Page {page_num} of {total_pages}")
                with info_col2:
                    st.info(f"📐 {width} x {height} px")
                with info_col3:
                    st.info(f"⏱️ {round(render_time)}ms")

            else:
                # Log error
                logger.log_error(
                    "PDF page render failed",
                    context={
                        "doc_id": doc_id,
                        "page": page_num,
                        "status_code": response.status_code,
                        "error": response.text[:200],
                    },
                )

                st.error(f"Failed to load page: {response.status_code}")
                if response.status_code == 404:
                    st.warning(
                        "PDF file not found. The document may have been moved or deleted."
                    )
                else:
                    st.text(response.text[:500])

    except Exception as e:
        if logger:
            logger.log_error(
                "PDF render exception",
                exception=e,
                context={"doc_id": doc_id, "page": page_num},
            )
        st.error(f"Error rendering PDF: {str(e)}")


def call_ask_api(
    query: str, api_base_url: str, params: Dict[str, Any], logger=None
) -> Dict[str, Any]:
    """Call the /ask API endpoint with logging"""
    if logger is None:
        logger = get_logger()

    try:
        url = f"{api_base_url}/ask"

        # IMPORTANT: Force execution_mode to production
        params["execution_mode"] = "production"

        payload = {
            "query": query,
            "hyde": params.get("hyde", True),
            "max_context": params.get("max_context", 8),
            "language": params.get("language", "vi"),
            "execution_mode": "production",  # Always use production mode
        }

        # Log API request
        logger.log_api_request(endpoint="/ask", method="POST", payload=payload)

        start_time = time.time()
        response = requests.post(url, json=payload, timeout=60)
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
            context={"timeout": 60, "api_base_url": api_base_url},
        )
        return {"success": False, "error": "Request timed out after 60 seconds"}
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


def format_citations_enhanced(citations: List[Dict]) -> pd.DataFrame:
    """Format citations with both score and confidence for display"""
    if not citations:
        return pd.DataFrame()

    formatted = []
    for i, cit in enumerate(citations, 1):
        # Get both score and confidence
        score = cit.get("score", 0)
        confidence = cit.get(
            "confidence", cit.get("relevance_score", 0)
        )  # fallback to relevance_score

        formatted.append(
            {
                "#": i,
                "Document": cit.get("doc_id", "Unknown"),
                "Page": cit.get("page", "N/A"),
                "Score": f"{score:.3f}",
                "Confidence": f"{confidence:.3f}",
                "Has BBox": "✓" if cit.get("bbox") else "✗",
                "Text Preview": (cit.get("text", "")[:100] + "...")
                if cit.get("text")
                else "N/A",
            }
        )

    return pd.DataFrame(formatted)


def render_citations_with_viewer(citations: List[Dict], api_base_url: str, logger=None):
    """Render citations table with PDF viewer buttons"""
    if not citations:
        st.info("No citations found")
        return

    # Initialize logger if not provided
    if logger is None:
        logger = get_logger()

    # Create the dataframe
    df_citations = format_citations_enhanced(citations)

    # Display as a table with custom rendering
    for idx, row in df_citations.iterrows():
        citation = citations[idx]

        # Create a container for each citation
        with st.container():
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(
                [0.5, 2, 1, 1, 1, 0.8, 3, 1.5]
            )

            with col1:
                st.text(row["#"])

            with col2:
                st.text(row["Document"])

            with col3:
                st.text(f"Page {row['Page']}")

            with col4:
                st.text(f"Score: {row['Score']}")

            with col5:
                st.text(f"Conf: {row['Confidence']}")

            with col6:
                st.text(row["Has BBox"])

            with col7:
                st.text(row["Text Preview"])

            with col8:
                # Add View Page button
                button_key = f"view_pdf_{idx}_{citation.get('doc_id', 'unknown')}_{citation.get('page', 0)}"
                if st.button("👁️ View Page", key=button_key, help="View PDF page"):
                    # Log the View Page click event
                    logger.log_button_click(
                        "view_pdf_page",
                        {
                            "doc_id": citation.get("doc_id", "Unknown"),
                            "page": citation.get("page", 0),
                            "citation_index": idx + 1,
                            "has_bbox": bool(citation.get("bbox")),
                            "confidence": citation.get("confidence", 0),
                        },
                    )

                    # Get the source path from citation - try pdf_path first (new field)
                    source_path = citation.get("pdf_path", "")
                    if not source_path:
                        # Fallback to old field locations for backward compatibility
                        source_path = citation.get("metadata", {}).get("source", "")
                        if not source_path:
                            source_path = citation.get("source", "")

                    if source_path and citation.get("page"):
                        # Log successful path resolution
                        logger.log_event(
                            EventType.INFO,
                            "PDF path resolved for viewing",
                            {
                                "doc_id": citation.get("doc_id", "Unknown"),
                                "page": citation.get("page"),
                                "path_found": True,
                                "path_source": "pdf_path"
                                if citation.get("pdf_path")
                                else "fallback",
                            },
                        )

                        # Store in session state to show the viewer
                        st.session_state[f"show_pdf_{idx}"] = {
                            "pdf_path": source_path,
                            "page_num": citation["page"],
                            "doc_id": citation.get("doc_id", "Unknown"),
                        }
                        st.rerun()
                    else:
                        # Log failure to find path
                        logger.log_event(
                            EventType.WARNING,
                            "PDF path not found for citation",
                            {
                                "doc_id": citation.get("doc_id", "Unknown"),
                                "page": citation.get("page"),
                                "has_pdf_path": bool(citation.get("pdf_path")),
                                "has_metadata_source": bool(
                                    citation.get("metadata", {}).get("source")
                                ),
                            },
                        )
                        st.warning("PDF path not available for this citation")

            st.divider()

    # Check if any PDF viewer should be shown
    for idx in range(len(citations)):
        if f"show_pdf_{idx}" in st.session_state:
            pdf_info = st.session_state[f"show_pdf_{idx}"]

            # Show PDF in an expander (expanded=True as per requirements)
            with st.expander(
                f"📄 Viewing: {pdf_info['doc_id']} - Page {pdf_info['page_num']}",
                expanded=True,
            ):
                # Pass logger to render_pdf_page for complete logging chain
                render_pdf_page(
                    api_base_url,
                    pdf_info["pdf_path"],
                    pdf_info["page_num"],
                    pdf_info["doc_id"],
                    logger=logger,
                )

                if st.button(f"Close Viewer", key=f"close_pdf_{idx}"):
                    # Log close event
                    logger.log_button_click(
                        "close_pdf_viewer",
                        {"doc_id": pdf_info["doc_id"], "page": pdf_info["page_num"]},
                    )
                    del st.session_state[f"show_pdf_{idx}"]
                    st.rerun()


def render(vision_mode=False):
    """Render improved query lab component with enhanced citations"""

    if vision_mode:
        st.header("👁️ Vision-Assisted Query Lab")
        st.caption("Query Lab with vision verification features enabled")
    else:
        st.header("🔍 Query Lab (Improved)")
        st.caption("Test and debug RAG pipeline with enhanced citation display")

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

    # Main layout
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Query Configuration")

        # Notice about production mode
        st.info("ℹ️ All queries will use **production mode** for optimal results")

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
        )

        # Quick presets (but execution mode will always be production)
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            if st.button("Cost Optimized", use_container_width=True, key="preset_cost"):
                st.session_state.preset = "cost"
                logger.log_button_click("preset_cost")
        with col_p2:
            if st.button(
                "Accuracy Focus", use_container_width=True, key="preset_accuracy"
            ):
                st.session_state.preset = "accuracy"
                logger.log_button_click("preset_accuracy")
        with col_p3:
            if st.button("Debug Mode", use_container_width=True, key="preset_debug"):
                st.session_state.preset = "debug"
                logger.log_button_click("preset_debug")

        # Apply presets if selected (but execution_mode stays production)
        preset = st.session_state.get("preset", None)
        if preset == "cost":
            default_k_bm25 = 30
            default_k_faiss = 30
            default_top_k = 5
            default_hyde = False
        elif preset == "accuracy":
            default_k_bm25 = 100
            default_k_faiss = 100
            default_top_k = 12
            default_hyde = True
        elif preset == "debug":
            default_k_bm25 = 50
            default_k_faiss = 50
            default_top_k = 8
            default_hyde = True
        else:
            default_k_bm25 = 50
            default_k_faiss = 50
            default_top_k = 8
            default_hyde = True

        # Execution mode - DISABLED, always production
        st.selectbox(
            "Execution Mode",
            options=["production"],
            index=0,
            help="Fixed to production mode for optimal results",
            disabled=True,
        )
        execution_mode = "production"  # Always production

        # HyDE settings
        with st.expander("HyDE Settings", expanded=False):
            enable_hyde = st.checkbox(
                "Enable HyDE",
                value=default_hyde,
                key="enable_hyde",
            )
            hyde_count = st.number_input(
                "HyDE Queries",
                min_value=1,
                max_value=5,
                value=2,
                key="hyde_count",
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

        # Run button
        if st.button(
            "🚀 Run Query", type="primary", use_container_width=True, key="run_query_btn"
        ):
            if query:
                # Start a new run
                st.session_state.run_id = logger.start_new_run()

                logger.log_button_click(
                    "run_query",
                    {
                        "query_length": len(query),
                        "execution_mode": "production",  # Always production
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
                            "execution_mode": "production",  # Always production
                            "hyde": enable_hyde,
                            "language": language,
                            "max_context": top_k_context,
                        },
                    },
                    performance_key="query_execution",
                )

                with st.spinner("Processing query..."):
                    # Prepare parameters
                    params = {
                        "max_context": top_k_context,
                        "execution_mode": "production",  # Force production
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

                        st.success("✓ Query completed successfully")
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
                    "📌 Citations (Enhanced)",
                    "Vision Verify",
                    "Metrics",
                    "Raw Data",
                ]
            )

            with tab1:
                # Overview Tab
                st.markdown("### 📝 Answer")
                answer_text = results.get("answer", "")

                # Check if answer is empty or too short
                if not answer_text or len(answer_text.strip()) < 10:
                    st.warning(
                        "⚠️ The system could not generate a complete answer. This may be due to:"
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
                    st.warning("⚠️ Warnings:")
                    for warn in warnings:
                        st.write(f"- {warn}")

            with tab2:
                # Retrieval Tab
                st.markdown("### 🔍 Retrieval Results")

                meta = results.get("meta", {})
                retrieval_info = meta.get("retrieval", {})

                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    st.markdown("**BM25 Results**")
                    bm25_results = retrieval_info.get("bm25_results", [])
                    st.write(f"Found {len(bm25_results)} documents")
                    if bm25_results:
                        for i, doc in enumerate(bm25_results[:5], 1):
                            st.caption(f"{i}. Score: {doc.get('score', 0):.3f}")

                with col_r2:
                    st.markdown("**FAISS Results**")
                    faiss_results = retrieval_info.get("faiss_results", [])
                    st.write(f"Found {len(faiss_results)} documents")
                    if faiss_results:
                        for i, doc in enumerate(faiss_results[:5], 1):
                            st.caption(f"{i}. Score: {doc.get('score', 0):.3f}")

                with col_r3:
                    st.markdown("**RRF Fused Results**")
                    fused_results = retrieval_info.get("fused_results", [])
                    st.write(f"Fused to {len(fused_results)} documents")
                    if fused_results:
                        for i, doc in enumerate(fused_results[:5], 1):
                            st.caption(f"{i}. Score: {doc.get('score', 0):.3f}")

            with tab3:
                # Rerank Tab
                st.markdown("### 📊 Reranking Details")

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
                st.markdown("### 🤖 Generation Details")

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
                # Enhanced Citations Tab
                st.markdown("### 📌 Enhanced Citations")
                st.caption(
                    "Showing both retrieval score and confidence for each citation"
                )

                citations = results.get("citations", [])
                if citations:
                    # Use the enhanced citation viewer with logging
                    render_citations_with_viewer(
                        citations, st.session_state.api_base_url, logger
                    )
                else:
                    st.info("No citations found")

            with tab6:
                # Vision Verify Tab
                if st.session_state.get("enable_vision_verify", False):
                    st.markdown("### 👁️ Vision Verification")

                    vision_info = meta.get("vision_verify", {})
                    if vision_info:
                        col_v1, col_v2, col_v3 = st.columns(3)
                        with col_v1:
                            pages_checked = vision_info.get("pages_checked", 0)
                            st.metric("Pages Checked", pages_checked)
                        with col_v2:
                            claims_verified = vision_info.get("claims_verified", 0)
                            st.metric("Claims Verified", claims_verified)
                        with col_v3:
                            verification_rate = vision_info.get("verification_rate", 0)
                            st.metric("Verification Rate", f"{verification_rate:.1%}")

                        corrections = vision_info.get("corrections", [])
                        if corrections:
                            st.markdown("**Corrections Applied:**")
                            for corr in corrections:
                                st.write(f"- {corr}")
                    else:
                        st.info("No vision verification data available")
                else:
                    st.warning(
                        "Vision Verification is disabled. Enable in sidebar settings."
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
            st.info("📝 Results will appear here after running a query")
            st.caption("Enter a query and click 'Run Query' to see results")

    # Timeline visualization at bottom
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
