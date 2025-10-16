"""
Query Lab Component - Improved version with enhanced citations
Phase 1 improvements:
- Show both score and confidence in citations
- Add PDF page viewer button
- Force execution_mode = production
- IEEE-style citations with direct PDF links
"""

import base64
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def convert_to_ieee_style(
    answer_text: str, citations: List[Dict], doc_number_map: Optional[Dict] = None
) -> Tuple[str, List[Dict]]:
    """
    Convert inline [Doc X, p.Y] citations to IEEE-style [n] format.

    Args:
        answer_text: The answer text containing [Doc X, p.Y] style citations
        citations: List of citation dicts from the API response
        doc_number_map: Optional mapping from doc_number to {doc_id, pdf_path, file_name}

    Returns:
        Tuple of (converted_text, ordered_citation_list)
        - converted_text: Answer with [1], [2], etc. instead of [Doc X, p.Y]
        - ordered_citation_list: List of unique citations in order of first appearance
          Each entry: {"doc_id", "file_name", "pages": [list], "pdf_path": str}
    """
    if not answer_text:
        return answer_text, []

    import re
    from pathlib import Path

    # Pattern to match [Doc X, p.Y] or [Doc X, pp. Y-Z] or [Doc X]
    # Also handles multiple citations in one bracket: [Doc 1, p.5; Doc 2, p.10]
    pattern = r"\[Doc\s+(\d+)(?:,\s*pp?\.?\s*([\d\-]+))?(?:;\s*Doc\s+(\d+)(?:,\s*pp?\.?\s*([\d\-]+))?)*\]"

    # Normalize doc_number_map keys to strings for uniform matching
    doc_number_map_str = {}
    if isinstance(doc_number_map, dict):
        for k, v in doc_number_map.items():
            doc_number_map_str[str(k)] = v

    # Build mappings collected from citations
    # 1) From doc_number -> citation info (legacy behavior)
    doc_citation_map = {}  # {doc_number: {doc_id, file_name, pages: set(), pdf_path}}
    # 2) From doc_id -> pages/pdf_path (new, to handle many doc_numbers -> one doc_id)
    doc_id_pages_map: Dict[str, Dict[str, Any]] = {}

    # First, populate from citations list (best source for page numbers)
    for cit in citations:
        doc_id = cit.get("doc_id", "Unknown")
        page = cit.get("page")
        pdf_path = cit.get("pdf_path", "")

        # Try to determine doc_number for this doc via doc_number_map (may be many)
        doc_number = None
        for num_key, doc_info in doc_number_map_str.items():
            if doc_info.get("doc_id") == doc_id:
                doc_number = str(num_key)
                pdf_path = doc_info.get("pdf_path", pdf_path)
                break

        # Extract file_name from pdf_path or doc_id
        file_name = doc_id
        if pdf_path:
            file_name = Path(pdf_path).name
        elif doc_id.startswith("DOCID_"):
            parts = doc_id.split("_")
            file_name = (
                "_".join(parts[1:-1])
                if len(parts) > 2
                else (parts[1] if len(parts) > 1 else doc_id)
            )

        # Store by doc_number (if any)
        if doc_number:
            if doc_number not in doc_citation_map:
                doc_citation_map[doc_number] = {
                    "doc_id": doc_id,
                    "file_name": file_name,
                    "pages": set(),
                    "pdf_path": pdf_path,
                }
            if page:
                try:
                    # Support pages like "5-7" by splitting and adding numbers
                    if isinstance(page, str) and "-" in page:
                        start, end = page.split("-", 1)
                        for p in range(int(start), int(end) + 1):
                            doc_citation_map[doc_number]["pages"].add(int(p))
                    else:
                        doc_citation_map[doc_number]["pages"].add(int(page))
                except Exception:
                    # Ignore non-integer pages
                    pass

        # Always store by doc_id (new robust map)
        if doc_id not in doc_id_pages_map:
            doc_id_pages_map[doc_id] = {
                "pages": set(),
                "pdf_path": pdf_path,
                "file_name": file_name,
            }
        if page:
            try:
                if isinstance(page, str) and "-" in page:
                    start, end = page.split("-", 1)
                    for p in range(int(start), int(end) + 1):
                        doc_id_pages_map[doc_id]["pages"].add(int(p))
                else:
                    doc_id_pages_map[doc_id]["pages"].add(int(page))
            except Exception:
                pass
        # Prefer non-empty pdf_path if missing previously
        if pdf_path and not doc_id_pages_map[doc_id].get("pdf_path"):
            doc_id_pages_map[doc_id]["pdf_path"] = pdf_path

    # Track unique citations in order of appearance
    citation_list: List[
        Dict
    ] = []  # Ordered list of {doc_id, file_name, pages: [list], pdf_path}
    citation_lookup: Dict[str, int] = {}  # Map doc_id -> citation index (1-based)

    converted_text = answer_text

    # Helper to ensure a doc_id is present in citation_list
    def ensure_citation_entry(
        doc_id: str, file_name: str, pages: List[int], pdf_path: str
    ) -> int:
        if doc_id not in citation_lookup:
            citation_list.append(
                {
                    "doc_id": doc_id,
                    "file_name": file_name,
                    "pages": sorted(list(set(pages))) if pages else [],
                    "pdf_path": pdf_path,
                }
            )
            citation_lookup[doc_id] = len(citation_list)
        return citation_lookup[doc_id]

    # Find all citation patterns and replace them
    def replace_citation(match):
        full_match = match.group(0)

        # Extract all Doc X patterns from the matched text
        doc_pattern = r"Doc\s+(\d+)(?:,\s*pp?\.?\s*([\d\-]+))?"
        doc_matches = list(re.finditer(doc_pattern, full_match))

        ieee_refs = []

        for doc_match in doc_matches:
            doc_num = str(doc_match.group(1))
            # 1) If we have citation info (with pages) for this doc number, use it
            if doc_num in doc_citation_map:
                cit_info = doc_citation_map[doc_num]
                doc_id = cit_info["doc_id"]
                ieee_num = ensure_citation_entry(
                    doc_id,
                    cit_info["file_name"],
                    list(cit_info["pages"]),
                    cit_info["pdf_path"],
                )
                ieee_refs.append(str(ieee_num))
            # 2) Otherwise, fall back to doc_number_map and try to merge with pages by doc_id
            elif doc_num in doc_number_map_str:
                info = doc_number_map_str[doc_num]
                doc_id = info.get("doc_id", f"doc_{doc_num}")
                file_name = info.get("file_name", doc_id)
                pdf_path = info.get("pdf_path", "")
                # Merge pages from any citations with the same doc_id
                pages_from_id = []
                if doc_id in doc_id_pages_map:
                    pages_from_id = list(doc_id_pages_map[doc_id]["pages"]) or []
                    if not pdf_path:
                        pdf_path = doc_id_pages_map[doc_id].get("pdf_path", "")
                    # Prefer better file name if available
                    if file_name == doc_id and doc_id_pages_map[doc_id].get(
                        "file_name"
                    ):
                        file_name = doc_id_pages_map[doc_id]["file_name"]
                ieee_num = ensure_citation_entry(
                    doc_id, file_name, pages_from_id, pdf_path
                )
                ieee_refs.append(str(ieee_num))
            else:
                # 3) Last-resort: keep the numeric label but no entry (should be rare)
                ieee_refs.append(doc_num)

        # Return IEEE-style reference
        if len(ieee_refs) == 1:
            return f"[{ieee_refs[0]}]"
        else:
            # Multiple citations: [1][2]
            return "".join([f"[{ref}]" for ref in ieee_refs])

    # Replace all citation patterns
    converted_text = re.sub(pattern, replace_citation, converted_text)

    # Post-process to remove duplicate consecutive citations like [1][1] -> [1]
    # Pattern: [N][N] where N is the same number
    dedupe_pattern = r"\[(\d+)\]\[\1\]"
    while re.search(dedupe_pattern, converted_text):
        converted_text = re.sub(dedupe_pattern, r"[\1]", converted_text)

    return converted_text, citation_list


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

        # Add tag filters if provided
        if "tags" in params and params["tags"]:
            payload["filters"] = {"tags": params["tags"]}

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


def format_citations_enhanced(citations: List[Dict]) -> pd.DataFrame:
    """Format citations with both score and confidence for display"""
    if not citations:
        return pd.DataFrame()

    formatted = []
    for i, cit in enumerate(citations, 1):
        # Get score (optional field from API)
        score_value = cit.get("score")
        if score_value is not None:
            score_display = f"{score_value:.3f}"
        else:
            score_display = "N/A"

        # Get confidence (priority field)
        confidence = cit.get("confidence", cit.get("relevance_score", None))
        if isinstance(confidence, (int, float)):
            confidence_display = f"{float(confidence):.3f}"
        else:
            confidence_display = "N/A"

        formatted.append(
            {
                "#": i,
                "Document": cit.get("doc_id", "Unknown"),
                "Page": cit.get("page", "N/A"),
                "Score": score_display,
                "Confidence": confidence_display,
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


def normalize_api_response(results: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize API response to unified UI-friendly structure.

    Transforms top-level retrieval_details, reranking_details, generation_details
    into a consistent ui dict for easier rendering.

    Args:
        results: Raw API response

    Returns:
        Normalized dict with ui['retrieval'], ui['rerank'], ui['generation'], ui['vision']
    """
    ui = {}

    # 1) Retrieval details
    retrieval_details = results.get("retrieval_details") or {}
    ui["retrieval"] = {
        "bm25": retrieval_details.get("bm25", []),
        "faiss": retrieval_details.get("faiss", []),
        "total_retrieved": retrieval_details.get("total_retrieved", 0),
        "from_cache": retrieval_details.get("from_cache", False),
    }

    # 2) Rerank details
    reranking_details = results.get("reranking_details") or {}
    ui["rerank"] = {
        "method": reranking_details.get("method", "unknown"),
        "results": reranking_details.get("results", []),
        "input_count": reranking_details.get("input_count", 0),
        "output_count": reranking_details.get("output_count", 0),
        "from_cache": reranking_details.get("from_cache", False),
    }

    # 3) Generation details
    meta = results.get("meta", {})
    generation_details = results.get("generation_details") or {}
    breakdown = meta.get("breakdown", {})

    ui["generation"] = {
        "model": generation_details.get("model")
        or meta.get("model_generation", "Unknown"),
        "latency_ms": breakdown.get("generate_ms", 0),
        "total_tokens": generation_details.get("total_tokens", 0),
        "estimated_cost": generation_details.get("estimated_cost", 0.0),
        "prompt_info": generation_details.get("prompt_info", {}),
        "tier": generation_details.get("tier", "unknown"),
        "language": generation_details.get("language", "unknown"),
        "confidence": generation_details.get("confidence", 0.0),
    }

    # 4) Vision details
    vision_meta = meta.get("vision_generation", {})
    vision_enabled = generation_details.get("vision_enabled", False)

    ui["vision"] = {
        "enabled": bool(vision_meta) or bool(vision_enabled),
        "pages_used": vision_meta.get("pages_used", []),
        "pages_failed": vision_meta.get("pages_failed", []),
    }

    return ui


def render(vision_mode=False):
    """Render query lab component with Material Design 3 styling"""

    # M3 Header with proper typography
    st.markdown(
        """
    <div class="md-card md-card-filled md-spacing-lg" style="margin-bottom: 24px;">
        <h1 class="md-typescale-headline-medium" style="margin: 0;">RAG Question Answering</h1>
        <p class="md-typescale-body-medium" style="margin: 8px 0 0 0; color: var(--md-sys-color-on-surface-variant);">
            Enterprise-grade document search and question answering system
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Initialize logger
    logger = get_logger(verbose=st.session_state.get("enable_verbose_logging", False))

    # Inject side sheet JS (once per render)
    try:
        from streamlit_app.components.side_sheet import render_side_sheet_js

        render_side_sheet_js()
    except ImportError:
        try:
            from components.side_sheet import render_side_sheet_js

            render_side_sheet_js()
        except:
            pass

    # Initialize session state
    if "query_results" not in st.session_state:
        st.session_state.query_results = None
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = os.getenv(
            "PVCFC_API_BASE_URL", "http://localhost:8000"
        )
    if "run_id" not in st.session_state:
        st.session_state.run_id = None

    # Query input with M3 styling
    st.markdown(
        '<div class="md-typescale-title-medium" style="margin-bottom: 8px;">Query Input</div>',
        unsafe_allow_html=True,
    )
    query = st.text_area(
        "Enter your question",
        placeholder="Enter your question here...\nExample: What are the operating specifications for ammonia storage tanks?",
        height=120,
        help="Enter technical questions about your documents",
        key="query_input",
        label_visibility="collapsed",
    )

    # Settings with M3 chips/segmented controls
    st.markdown(
        '<div class="md-typescale-title-medium" style="margin: 24px 0 8px 0;">Configuration</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        st.markdown(
            '<div class="md-typescale-label-large" style="margin-bottom: 4px;">Language</div>',
            unsafe_allow_html=True,
        )
        # Use chips for language selection
        lang_col1, lang_col2 = st.columns(2)
        with lang_col1:
            if st.button(
                "🇻🇳 Vietnamese",
                key="lang_vi",
                use_container_width=True,
                type="primary"
                if st.session_state.get("selected_lang", "vi") == "vi"
                else "secondary",
            ):
                st.session_state.selected_lang = "vi"
        with lang_col2:
            if st.button(
                "🇬🇧 English",
                key="lang_en",
                use_container_width=True,
                type="primary"
                if st.session_state.get("selected_lang", "vi") == "en"
                else "secondary",
            ):
                st.session_state.selected_lang = "en"

        language = st.session_state.get("selected_lang", "vi")

    with col2:
        st.markdown(
            '<div class="md-typescale-label-large" style="margin-bottom: 4px;">Context Chunks</div>',
            unsafe_allow_html=True,
        )
        max_context = st.number_input(
            "Context Chunks",
            min_value=1,
            max_value=20,
            value=8,
            help="Number of document chunks to retrieve",
            label_visibility="collapsed",
        )

    with col3:
        st.markdown(
            '<div class="md-card md-card-outlined md-spacing-sm" style="margin-top: 24px; text-align: center;">'
            '<div class="md-typescale-label-small" style="color: var(--md-sys-color-on-surface-variant);">ACTIVE FEATURES</div>'
            '<div class="md-typescale-body-small" style="margin-top: 4px;">Vision + Reranking</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    # Vision and Re-ranking are ALWAYS enabled (hardcoded)
    enable_vision = True
    use_rerank = True

    # Advanced options - minimal
    with st.expander("Advanced Options", expanded=False):
        st.markdown("**P&ID Tag Filter** 🏷️")
        st.caption("Filter documents by equipment tags (e.g., E04217, P-101, V-2051)")

        # Fetch available tags from API
        if "available_tags" not in st.session_state:
            try:
                tags_response = requests.get(
                    f"{st.session_state.api_base_url}/tags", timeout=5
                )
                if tags_response.ok:
                    tags_data = tags_response.json()
                    st.session_state.available_tags = tags_data.get("tags", [])
                else:
                    st.session_state.available_tags = []
            except Exception:
                st.session_state.available_tags = []

        # Show tag filter UI
        available_tags = st.session_state.available_tags
        if available_tags:
            # Multi-select for tags
            selected_tags = st.multiselect(
                "Select Tags",
                options=available_tags,
                default=[],
                help=f"{len(available_tags)} tags available in the system",
                key="tag_filter",
                label_visibility="collapsed",
            )

            if selected_tags:
                st.info(
                    f"📌 Filtering by {len(selected_tags)} tag(s): {', '.join(selected_tags[:5])}{'...' if len(selected_tags) > 5 else ''}"
                )
            else:
                st.caption(
                    f"✓ {len(available_tags)} tags available (no filter applied)"
                )
        else:
            st.caption("⚠️ Tag filtering unavailable (OpenSearch may be disconnected)")

        st.divider()

        st.markdown("**Citation Format**")
        use_ieee_citations = st.checkbox(
            "Use IEEE-style Citations",
            value=True,
            help="Numbered citation format [1], [2] with references section",
        )
        st.caption("Standard academic citation style")

        st.divider()

        st.markdown("**System Information**")
        st.caption("Retrieval: Weaviate (semantic) + OpenSearch (keyword)")
        st.caption("Reranking: BGE Cross-Encoder")
        st.caption("Vision: Gemini Multimodal")
        st.caption(f"P&ID Tags: {len(available_tags)} tags indexed")

    # Set defaults for hidden parameters
    execution_mode = "production"  # Always production
    top_k_context = max_context

    # Run button with M3 styling
    st.markdown("<br>", unsafe_allow_html=True)

    # Add loading indicator if processing
    if st.session_state.get("query_processing", False):
        st.markdown('<div class="md-progress-linear"></div>', unsafe_allow_html=True)

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
                        "hyde": True,
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
                    "hyde": True,
                }

                # Add tag filters if selected
                selected_tags = st.session_state.get("tag_filter", [])
                if selected_tags:
                    params["tags"] = selected_tags

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
                            "citations_count": len(result["data"].get("citations", [])),
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

    # Results section with M3 styling
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="md-typescale-title-large" style="margin-bottom: 16px;">Results</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.query_results:
        results = st.session_state.query_results

        # Normalize API response for consistent UI rendering
        ui = normalize_api_response(results)
        # Keep meta available for metrics and timeline tabs
        meta = results.get("meta", {})

        # Result tabs - clean
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
            [
                "Overview",
                "Retrieval",
                "Rerank",
                "Generation",
                "Vision",
                "Metrics",
                "Raw Data",
            ]
        )

        with tab1:
            # Overview Tab
            st.markdown("### Answer")

            answer_text = results.get("answer", "")
            citations = results.get("citations", [])
            # Fetch doc_number_map from the correct location
            # Prefer generation_details.metadata.doc_number_map, fallback to meta.doc_number_map
            # CRITICAL FIX: Also check vision_generation paths for Vision-enabled answers
            doc_number_map = {}
            try:
                # Priority 1: generation_details.metadata.doc_number_map
                gen_meta = (
                    results.get("generation_details", {})
                    .get("metadata", {})
                    .get("doc_number_map")
                )
                if gen_meta:
                    doc_number_map = gen_meta
                # Priority 2: generation_details.metadata.vision_generation.doc_number_map
                elif (
                    results.get("generation_details", {})
                    .get("metadata", {})
                    .get("vision_generation", {})
                    .get("doc_number_map")
                ):
                    doc_number_map = (
                        results.get("generation_details", {})
                        .get("metadata", {})
                        .get("vision_generation", {})
                        .get("doc_number_map")
                    )
                # Priority 3: meta.doc_number_map
                elif results.get("meta", {}).get("doc_number_map"):
                    doc_number_map = results.get("meta", {}).get("doc_number_map")
                # Priority 4: meta.vision_generation.doc_number_map
                elif (
                    results.get("meta", {})
                    .get("vision_generation", {})
                    .get("doc_number_map")
                ):
                    doc_number_map = (
                        results.get("meta", {})
                        .get("vision_generation", {})
                        .get("doc_number_map")
                    )

                # FALLBACK: If still empty, build from citations directly
                if not doc_number_map and citations:
                    doc_number_map = {}
                    for idx, cit in enumerate(citations, 1):
                        doc_id = cit.get("doc_id", "")
                        pdf_path = cit.get("pdf_path", "")
                        if doc_id:
                            # Extract file name from pdf_path or doc_id
                            file_name = doc_id
                            if pdf_path:
                                from pathlib import Path

                                file_name = Path(pdf_path).name
                            elif doc_id.startswith("DOCID_"):
                                parts = doc_id.split("_")
                                file_name = (
                                    "_".join(parts[1:-1])
                                    if len(parts) > 2
                                    else (parts[1] if len(parts) > 1 else doc_id)
                                )

                            doc_number_map[str(idx)] = {
                                "doc_id": doc_id,
                                "pdf_path": pdf_path,
                                "file_name": file_name,
                            }
            except Exception as e:
                # Last resort: build from citations
                doc_number_map = {}
                if citations:
                    for idx, cit in enumerate(citations, 1):
                        doc_id = cit.get("doc_id", "")
                        pdf_path = cit.get("pdf_path", "")
                        if doc_id:
                            from pathlib import Path

                            file_name = Path(pdf_path).name if pdf_path else doc_id
                            doc_number_map[str(idx)] = {
                                "doc_id": doc_id,
                                "pdf_path": pdf_path,
                                "file_name": file_name,
                            }

            # Check if IEEE-style citations is enabled
            use_ieee = st.session_state.get("use_ieee_citations", True)

            # DEBUG: Log raw data
            with st.expander("🔍 DEBUG: Raw Data", expanded=False):
                st.json(
                    {
                        "answer_text_preview": answer_text[:500]
                        if answer_text
                        else None,
                        "citations_count": len(citations),
                        "citations_sample": [
                            {
                                "doc_id": c.get("doc_id"),
                                "page": c.get("page"),
                                "pdf_path": c.get("pdf_path", "")[:80] + "..."
                                if c.get("pdf_path")
                                else None,
                            }
                            for c in citations[:3]
                        ],
                        "doc_number_map_keys": list(doc_number_map.keys())
                        if doc_number_map
                        else [],
                        "doc_number_map_sample": {
                            k: v for k, v in list(doc_number_map.items())[:3]
                        }
                        if doc_number_map
                        else {},
                    }
                )

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
                # Convert to IEEE style if enabled
                if use_ieee and citations:
                    converted_answer, ieee_citation_list = convert_to_ieee_style(
                        answer_text, citations, doc_number_map
                    )
                    st.markdown(converted_answer)
                else:
                    st.markdown(answer_text)

            # Display metrics cards with M3 styling
            st.markdown("<br>", unsafe_allow_html=True)
            col_m1, col_m2, col_m3 = st.columns(3)

            with col_m1:
                confidence = results.get("confidence", 0.0)
                # Use M3 color roles for semantic meaning
                if confidence > 0.7:
                    conf_color = "var(--md-sys-color-tertiary)"
                elif confidence > 0.5:
                    conf_color = "var(--md-sys-color-secondary)"
                else:
                    conf_color = "var(--md-sys-color-error)"

                st.markdown(
                    f"""
                    <div class="md-card md-card-elevated md-spacing-md" style="text-align: center;">
                        <div class="md-typescale-label-small" style="color: var(--md-sys-color-on-surface-variant); margin-bottom: 8px;">CONFIDENCE</div>
                        <div class="md-typescale-headline-small" style="color: {conf_color};">{confidence:.0%}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col_m2:
                num_citations = len(results.get("citations", []))
                st.markdown(
                    f"""
                    <div class="md-card md-card-elevated md-spacing-md" style="text-align: center;">
                        <div class="md-typescale-label-small" style="color: var(--md-sys-color-on-surface-variant); margin-bottom: 8px;">CITATIONS</div>
                        <div class="md-typescale-headline-small" style="color: var(--md-sys-color-primary);">{num_citations}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col_m3:
                total_latency = results.get("total_latency_ms", 0)
                # Semantic color for latency
                if total_latency < 3000:
                    latency_color = "var(--md-sys-color-tertiary)"
                elif total_latency < 5000:
                    latency_color = "var(--md-sys-color-secondary)"
                else:
                    latency_color = "var(--md-sys-color-error)"

                st.markdown(
                    f"""
                    <div class="md-card md-card-elevated md-spacing-md" style="text-align: center;">
                        <div class="md-typescale-label-small" style="color: var(--md-sys-color-on-surface-variant); margin-bottom: 8px;">LATENCY</div>
                        <div class="md-typescale-headline-small" style="color: {latency_color};">{total_latency:.0f}<span class="md-typescale-body-small" style="color: var(--md-sys-color-on-surface-variant);">ms</span></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Warnings
            warnings = results.get("warnings", [])
            if warnings:
                st.warning("⚠️ Warnings:")
                for warn in warnings:
                    st.write(f"- {warn}")

            # References section with Side Sheet option
            if citations:
                st.markdown("<br>", unsafe_allow_html=True)

                col_ref1, col_ref2 = st.columns([4, 1])
                with col_ref1:
                    st.markdown("### References")
                with col_ref2:
                    # Button to open side sheet with all citations
                    if st.button(
                        "📋 View in Panel",
                        key="open_ref_sheet",
                        use_container_width=True,
                        help="Open citations in side panel",
                    ):
                        st.session_state.show_citations_sheet = True
                        st.rerun()

                if use_ieee and "ieee_citation_list" in locals():
                    # IEEE-style references

                    from urllib.parse import urlencode

                    for idx, ref in enumerate(ieee_citation_list, 1):
                        file_name = ref.get("file_name", "Unknown")
                        pages = ref.get("pages", [])
                        pdf_path = ref.get("pdf_path", "")

                        # Display reference number and file name
                        st.markdown(f"**[{idx}]** {file_name}")

                        # Display pages with links
                        if pages and pdf_path:
                            page_links = []
                            for page in pages:
                                # Try to build PDF link with fallback to image
                                try:
                                    # Check if PDF file exists
                                    import os
                                    from pathlib import Path

                                    pdf_exists = (
                                        os.path.exists(pdf_path) if pdf_path else False
                                    )

                                    if pdf_exists:
                                        # Build URL for PDF open endpoint (native PDF viewing)
                                        # We need both: page query param for API and #page=N fragment for browser
                                        # The #page=N fragment tells browser's PDF viewer where to scroll to
                                        params = {
                                            "pdf_path": pdf_path,
                                            "page": str(page),
                                        }
                                        params_str = urlencode(params)
                                        # Add #page=N fragment for browser PDF viewer to auto-scroll
                                        pdf_url = f"{st.session_state.api_base_url}/api/pdf/open?{params_str}#page={page}"
                                        page_links.append(
                                            f'<a href="{pdf_url}" target="_blank" style="margin-right: 8px;" title="Open PDF at page {page}">p.{page}</a>'
                                        )
                                    else:
                                        # Fallback to image render endpoint
                                        params = {
                                            "pdf_path": pdf_path,
                                            "page_num": str(page),
                                            "dpi": "200",
                                            "format": "png",
                                        }
                                        params_str = urlencode(params)
                                        img_url = f"{st.session_state.api_base_url}/api/pdf/render-page?{params_str}"
                                        page_links.append(
                                            f'<a href="{img_url}" target="_blank" style="margin-right: 8px;" title="View page {page} as image (PDF not found)">⚠️ p.{page}</a>'
                                        )
                                except Exception as e:
                                    # If any error, provide image fallback
                                    params = {
                                        "pdf_path": pdf_path,
                                        "page_num": str(page),
                                        "dpi": "200",
                                        "format": "png",
                                    }
                                    params_str = urlencode(params)
                                    img_url = f"{st.session_state.api_base_url}/api/pdf/render-page?{params_str}"
                                    page_links.append(
                                        f'<a href="{img_url}" target="_blank" style="margin-right: 8px;" title="View page {page} as image">⚠️ p.{page}</a>'
                                    )

                            st.markdown(
                                "&nbsp;&nbsp;&nbsp;&nbsp;" + " ".join(page_links),
                                unsafe_allow_html=True,
                            )
                        elif pages:
                            # No PDF path, just show page numbers
                            pages_str = ", ".join([f"p.{p}" for p in pages])
                            st.caption(f"    {pages_str}")
                else:
                    # Traditional sources section
                    st.markdown("### 📚 Referenced Sources")

                    # Extract unique doc_ids with their details
                    unique_sources = {}
                    for cit in citations:
                        doc_id = cit.get("doc_id", "Unknown")
                        if doc_id not in unique_sources:
                            # Try to get file_name from doc_id (parse the readable part)
                            # Format: DOCID_<readable_part>_<hash>
                            file_name = doc_id
                            if doc_id.startswith("DOCID_"):
                                parts = doc_id.split("_")
                                if len(parts) > 1:
                                    # Join all parts except the last hash part
                                    file_name = (
                                        "_".join(parts[1:-1])
                                        if len(parts) > 2
                                        else parts[1]
                                    )

                            unique_sources[doc_id] = {
                                "file_name": file_name,
                                "pages": set(),
                            }

                        # Collect all pages referenced from this document
                        page = cit.get("page")
                        if page:
                            unique_sources[doc_id]["pages"].add(page)

                    # Display each unique source
                    for idx, (doc_id, info) in enumerate(unique_sources.items(), 1):
                        pages_list = sorted(list(info["pages"]))
                        pages_str = (
                            ", ".join([f"p.{p}" for p in pages_list])
                            if pages_list
                            else "N/A"
                        )

                        with st.expander(
                            f"📄 {idx}. {info['file_name']}", expanded=False
                        ):
                            st.caption(f"**Document ID:** `{doc_id}`")
                            st.caption(f"**Referenced Pages:** {pages_str}")

                            # Show snippet from first citation of this document
                            first_cit = next(
                                (c for c in citations if c.get("doc_id") == doc_id),
                                None,
                            )
                            if first_cit and first_cit.get("text_snippet"):
                                st.text(first_cit["text_snippet"][:200] + "...")

        with tab2:
            # Retrieval Tab
            st.markdown("### 🔍 Retrieval Results")

            retrieval_info = ui["retrieval"]

            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.markdown("**BM25 Results**")
                bm25_results = retrieval_info.get("bm25", [])
                st.write(f"Found {len(bm25_results)} documents")
                if bm25_results:
                    for i, doc in enumerate(bm25_results[:5], 1):
                        st.caption(
                            f"{i}. {doc.get('doc_id', 'N/A')[:30]}... - Score: {doc.get('score', 0):.3f}"
                        )

            with col_r2:
                st.markdown("**FAISS Results**")
                faiss_results = retrieval_info.get("faiss", [])
                st.write(f"Found {len(faiss_results)} documents")
                if faiss_results:
                    for i, doc in enumerate(faiss_results[:5], 1):
                        st.caption(
                            f"{i}. {doc.get('doc_id', 'N/A')[:30]}... - Score: {doc.get('score', 0):.3f}"
                        )

            with col_r3:
                st.markdown("**Total Retrieved**")
                total = retrieval_info.get("total_retrieved", 0)
                from_cache = retrieval_info.get("from_cache", False)
                st.metric("Documents", total)
                if from_cache:
                    st.caption("✓ From cache")

        with tab3:
            # Rerank Tab
            st.markdown("### 📊 Reranking Details")

            rerank_info = ui["rerank"]

            col_rr1, col_rr2, col_rr3 = st.columns(3)
            with col_rr1:
                input_count = rerank_info.get("input_count", 0)
                st.metric("Input", f"{input_count} docs")
            with col_rr2:
                output_count = rerank_info.get("output_count", 0)
                st.metric("Output", f"{output_count} docs")
            with col_rr3:
                method = rerank_info.get("method", "unknown")
                st.metric("Method", method)

            # Show reranked results
            st.markdown("**Top Reranked Results:**")
            reranked = rerank_info.get("results", [])
            if reranked:
                for result in reranked[:10]:
                    rank = result.get("rank", 0)
                    doc_id = result.get("doc_id", "Unknown")[:50]
                    score = result.get("score", 0)
                    page = result.get("page", "N/A")
                    text_preview = result.get("text", "")[:80]
                    st.caption(f"{rank}. {doc_id} (p.{page}) - Score: {score:.4f}")
                    if text_preview:
                        st.text(f"   {text_preview}...")
            else:
                st.info("No reranking results available")

        with tab4:
            # Generation Tab
            st.markdown("### 🤖 Generation Details")

            gen_info = ui["generation"]

            col_g1, col_g2, col_g3, col_g4 = st.columns(4)
            with col_g1:
                model = gen_info.get("model", "Unknown")
                st.metric("Model", model)
            with col_g2:
                latency = gen_info.get("latency_ms", 0)
                st.metric("Latency", f"{latency:.0f}ms")
            with col_g3:
                tokens = gen_info.get("total_tokens", 0)
                st.metric("Total Tokens", tokens if tokens > 0 else "N/A")
            with col_g4:
                cost = gen_info.get("estimated_cost", 0)
                st.metric("Est. Cost", f"${cost:.4f}" if cost > 0 else "N/A")

            # Additional generation info
            col_g5, col_g6 = st.columns(2)
            with col_g5:
                tier = gen_info.get("tier", "unknown")
                st.caption(f"**Tier:** {tier}")
            with col_g6:
                language = gen_info.get("language", "unknown")
                st.caption(f"**Language:** {language}")

            # Prompt snapshot (redacted)
            st.markdown("**Prompt Structure**")
            prompt_info = gen_info.get("prompt_info", {})
            if prompt_info:
                st.json(prompt_info)
            else:
                st.info("Prompt info not available")

        with tab5:
            # Vision Verify Tab - Check if vision was actually used in generation
            vision_info = ui["vision"]

            if vision_info.get("enabled", False):
                st.markdown("### 👁️ Vision Generation Used")

                pages_used = vision_info.get("pages_used", [])
                pages_failed = vision_info.get("pages_failed", [])

                if pages_used or pages_failed:
                    col_v1, col_v2, col_v3 = st.columns(3)
                    with col_v1:
                        st.metric("PDF Pages Used", len(pages_used))
                    with col_v2:
                        st.metric("Pages Failed", len(pages_failed))
                    with col_v3:
                        total_pages = len(pages_used) + len(pages_failed)
                        success_rate = (
                            (len(pages_used) / total_pages * 100)
                            if total_pages > 0
                            else 0
                        )
                        st.metric("Success Rate", f"{success_rate:.1f}%")

                    # Show page details
                    if pages_used:
                        st.markdown("**PDF Pages Processed:**")
                        for page_info in pages_used:
                            page_num = page_info.get("page", "N/A")
                            pdf_path = page_info.get("pdf_path", "Unknown")
                            # Extract filename from path
                            import os

                            filename = (
                                os.path.basename(pdf_path)
                                if pdf_path != "Unknown"
                                else "Unknown"
                            )
                            st.write(f"- Page {page_num} from {filename[:60]}...")
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

        with tab6:
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

        with tab7:
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
            # Detect cache hit (retrieve_ms = 0 AND rerank_ms = 0)
            retrieve_ms = breakdown.get("retrieve_ms", 0)
            rerank_ms = breakdown.get("rerank_ms", 0)
            cache_hit = retrieve_ms == 0 and rerank_ms == 0

            # Detect BGE reranking (rerank_ms = 0 but retrieve_ms > 0)
            bge_enabled = rerank_ms == 0 and retrieve_ms > 0

            # Calculate total time
            total_time = sum(breakdown.values())

            # Show header with cache status
            if cache_hit:
                st.write(
                    f"**Total Processing Time: {total_time:.0f}ms** ⚡ *(Cache Hit)*"
                )
                st.caption("Retrieval and reranking results were served from cache")
            else:
                st.write(f"**Total Processing Time: {total_time:.0f}ms**")

            # Stage labels mapping
            stage_labels = {
                "transform_ms": "1️⃣ Query Transform",
                "retrieve_ms": "2️⃣ Hybrid Retrieval"
                + (" (incl. BGE Rerank)" if bge_enabled else ""),
                "rerank_ms": "3️⃣ Reranking",
                "generate_ms": "4️⃣ Generation",
                "cove_ms": "5️⃣ Chain-of-Verification",
            }

            # Create a horizontal bar for each stage (skip zero-time stages unless cache hit)
            for stage, time_ms in breakdown.items():
                # Skip rerank_ms display if BGE is enabled (it's included in retrieve_ms)
                if stage == "rerank_ms" and bge_enabled:
                    continue

                percentage = (time_ms / total_time * 100) if total_time > 0 else 0
                label = stage_labels.get(stage, stage)

                # Color based on percentage
                if percentage > 50:
                    color = "🔴"  # Red for high
                elif percentage > 20:
                    color = "🟡"  # Yellow for medium
                else:
                    color = "🟢"  # Green for low

                st.progress(percentage / 100)
                st.caption(f"{color} {label}: {time_ms:.0f}ms ({percentage:.1f}%)")
        else:
            st.info("No timing data available for this query")

    # Render citations side sheet if opened
    if (
        st.session_state.get("show_citations_sheet", False)
        and st.session_state.query_results
    ):
        results = st.session_state.query_results
        citations = results.get("citations", [])

        if citations:
            try:
                from streamlit_app.components.side_sheet import (
                    render_citation_side_sheet,
                )

                render_citation_side_sheet(
                    citations=citations,
                    api_base_url=st.session_state.api_base_url,
                    selected_citation_idx=0,
                )
            except ImportError:
                try:
                    from components.side_sheet import render_citation_side_sheet

                    render_citation_side_sheet(
                        citations=citations,
                        api_base_url=st.session_state.api_base_url,
                        selected_citation_idx=0,
                    )
                except Exception as e:
                    st.error(f"Could not load side sheet: {e}")
