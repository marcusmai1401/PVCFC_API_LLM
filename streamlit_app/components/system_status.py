"""
System Status Component
Gọi API /healthz và /index-stats để hiển thị trạng thái hệ thống
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests
import streamlit as st


def fetch_health_status(api_base_url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Fetch health status from /healthz endpoint

    Args:
        api_base_url: Base URL of the API
        timeout: Request timeout in seconds

    Returns:
        Health status data or error info
    """
    try:
        response = requests.get(f"{api_base_url}/healthz", timeout=timeout)

        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json(),
                "response_time_ms": response.elapsed.total_seconds() * 1000,
            }
        else:
            return {
                "success": False,
                "error": f"Status code: {response.status_code}",
                "data": None,
            }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout", "data": None}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Connection failed", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def fetch_index_stats(api_base_url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Fetch index statistics from /index-stats endpoint

    Args:
        api_base_url: Base URL of the API
        timeout: Request timeout in seconds

    Returns:
        Index stats data or error info
    """
    try:
        response = requests.get(f"{api_base_url}/index-stats", timeout=timeout)

        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json(),
                "response_time_ms": response.elapsed.total_seconds() * 1000,
            }
        else:
            return {
                "success": False,
                "error": f"Status code: {response.status_code}",
                "data": None,
            }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout", "data": None}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Connection failed", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def render_system_status(api_base_url: str = None):
    """
    Render the System Status section with iOS styling

    Args:
        api_base_url: API base URL (uses session state if not provided)
    """

    # Use provided URL or get from session state
    if api_base_url is None:
        api_base_url = st.session_state.get("api_base_url", "http://localhost:8000")

    # iOS-style section header
    st.markdown(
        """
    <div class="ios-card" style="margin-bottom: 24px;">
        <h2 class="ios-title" style="margin: 0;">System Status</h2>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Create refresh button
    col1, col2, col3 = st.columns([2, 1, 3])
    with col2:
        refresh = st.button("Refresh", use_container_width=True)

    # Initialize or refresh data
    if refresh or "system_status_cache" not in st.session_state:
        with st.spinner("Checking system status..."):
            # Fetch health status
            health_result = fetch_health_status(api_base_url)

            # Fetch index stats
            index_result = fetch_index_stats(api_base_url)

            # Cache results
            st.session_state.system_status_cache = {
                "health": health_result,
                "index": index_result,
                "timestamp": datetime.now().isoformat(),
            }

    # Get cached data
    cached_data = st.session_state.get("system_status_cache", {})
    health_result = cached_data.get("health", {})
    index_result = cached_data.get("index", {})
    cache_time = cached_data.get("timestamp")

    # Display last update time
    if cache_time:
        st.markdown(
            f'<p class="ios-caption" style="text-align: center; margin-bottom: 16px;">Last updated: {cache_time}</p>',
            unsafe_allow_html=True,
        )

    # Display Health Status with iOS cards
    if health_result.get("success"):
        health_data = health_result["data"]

        # Main status in iOS-style cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            status = health_data.get("status", "unknown")
            status_color = "#34c759" if status == "healthy" else "#ff3b30"
            st.markdown(
                f"""
            <div class="ios-card-compact" style="text-align: center;">
                <p class="ios-caption" style="margin: 0 0 8px 0;">Status</p>
                <p class="ios-title" style="margin: 0; color: {status_color};">{status.title()}</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with col2:
            env = health_data.get("app_env", "unknown")
            st.markdown(
                f"""
            <div class="ios-card-compact" style="text-align: center;">
                <p class="ios-caption" style="margin: 0 0 8px 0;">Environment</p>
                <p class="ios-title" style="margin: 0;">{env.upper()}</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with col3:
            version = health_data.get("version", "unknown")
            st.markdown(
                f"""
            <div class="ios-card-compact" style="text-align: center;">
                <p class="ios-caption" style="margin: 0 0 8px 0;">Version</p>
                <p class="ios-title" style="margin: 0;">v{version}</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with col4:
            uptime = health_data.get("uptime_human", "unknown")
            st.markdown(
                f"""
            <div class="ios-card-compact" style="text-align: center;">
                <p class="ios-caption" style="margin: 0 0 8px 0;">Uptime</p>
                <p class="ios-title" style="margin: 0;">{uptime}</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # LLM Provider info
        col1, col2 = st.columns(2)
        with col1:
            provider = health_data.get("llm_provider", "unknown")
            st.metric("LLM Provider", provider)

        with col2:
            llm_ready = health_data.get("llm_provider_ready", False)
            if llm_ready:
                st.metric("LLM Status", "Ready", delta="Active")
            else:
                st.metric("LLM Status", "Not Ready", delta="-Inactive")

        # Response time (with null safety)
        response_time = health_result.get("response_time_ms")
        if response_time is not None:
            st.markdown(
                f'<p class="ios-caption" style="margin-top: 12px; text-align: center;">Response time: {float(response_time):.0f}ms</p>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f"""
        <div class="ios-card" style="border-left: 3px solid #ff3b30;">
            <p class="ios-body" style="margin: 0; color: #ff3b30;">
                API Health Check Failed: {health_result.get('error', 'Unknown error')}
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Display Index Statistics
    st.markdown(
        """
    <div class="ios-card" style="margin-bottom: 16px;">
        <h3 class="ios-title" style="margin: 0;">Index Statistics</h3>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if index_result.get("success"):
        stats_data = index_result.get("data", {})

        # Check if we have the expected structure
        if "bm25_documents" in stats_data:
            # Using retriever.get_statistics() format
            col1, col2, col3 = st.columns(3)

            with col1:
                bm25_count = stats_data.get("bm25_documents", 0)
                if bm25_count > 0:
                    st.success(f"✅ BM25 Index")
                    st.metric("Documents", f"{bm25_count:,}")
                else:
                    st.warning("⚠️ BM25 Index")
                    st.metric("Documents", "0")

            with col2:
                faiss_count = stats_data.get("faiss_documents", 0)
                if faiss_count > 0:
                    st.success(f"✅ FAISS Index")
                    st.metric("Vectors", f"{faiss_count:,}")
                else:
                    st.warning("⚠️ FAISS Index")
                    st.metric("Vectors", "0")

            with col3:
                # Display configuration
                config = stats_data.get("config", {})
                st.info("⚙️ Configuration")
                st.caption(f"k_bm25: {config.get('k_bm25', 'N/A')}")
                st.caption(f"k_faiss: {config.get('k_faiss', 'N/A')}")
                st.caption(f"HyDE: {config.get('use_hyde', False)}")

        elif "bm25" in stats_data or "faiss" in stats_data or "weaviate" in stats_data:
            # Using index manager format - support Weaviate, Legacy FAISS, and Hybrid Modern
            retriever_type = stats_data.get("retriever_type", "unknown")

            if (
                retriever_type == "hybrid_modern"
                or retriever_type == "hybrid_with_tags"
            ):
                # Modern Hybrid mode (Weaviate + OpenSearch + optional P&ID Tags)
                if retriever_type == "hybrid_with_tags":
                    st.write("Hybrid Retrieval: Weaviate + OpenSearch + P&ID Tags")
                else:
                    st.write("Hybrid Retrieval: Weaviate + OpenSearch")

                weaviate_stats = stats_data.get("weaviate", {})
                opensearch_stats = stats_data.get("opensearch", {})

                col1, col2 = st.columns(2)

                with col1:
                    status = weaviate_stats.get("status", "unknown")
                    collection = weaviate_stats.get("collection", "N/A")
                    ready = weaviate_stats.get("ready", False)
                    st.metric("Weaviate Status", status)
                    st.metric("Collection", collection)
                    st.metric("Ready", "Yes" if ready else "No")

                with col2:
                    index_name = opensearch_stats.get("index_name", "N/A")
                    num_docs = opensearch_stats.get("num_documents", 0)
                    store_size = opensearch_stats.get("store_size_human", "N/A")
                    st.metric("OpenSearch Index", index_name)
                    st.metric("Documents", f"{num_docs:,}")
                    st.metric("Store Size", store_size)

            elif retriever_type == "weaviate":
                # Weaviate mode (Phase 4)
                st.write("Vector Database: Weaviate")

                weaviate_stats = stats_data.get("weaviate", {})
                if weaviate_stats.get("loaded"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Collection", weaviate_stats.get("collection", "N/A"))
                    with col2:
                        ready = "Ready" if weaviate_stats.get("ready") else "Not Ready"
                        st.metric("Status", ready)
                else:
                    st.warning("Weaviate Not Connected")
                    st.caption("Weaviate is not available")

            elif retriever_type == "faiss":
                # FAISS mode (Legacy)
                st.write("Retrieval: Hybrid BM25 + FAISS (Legacy)")
                col1, col2 = st.columns(2)

                # BM25 Stats
                with col1:
                    bm25_stats = stats_data.get("bm25", {})
                    if bm25_stats.get("loaded"):
                        doc_count = bm25_stats.get("doc_count", 0)
                        chunk_count = bm25_stats.get("chunk_count", 0)
                        st.metric("Documents", f"{doc_count:,}")
                        st.metric("Chunks", f"{chunk_count:,}")
                    else:
                        st.caption("BM25 index not loaded")

                # FAISS Stats
                with col2:
                    faiss_stats = stats_data.get("faiss", {})
                    if faiss_stats.get("loaded"):
                        vector_count = faiss_stats.get("vector_count", 0)
                        dimension = faiss_stats.get("dimension", 0)
                        st.metric("Vectors", f"{vector_count:,}")
                        st.metric("Dimension", dimension)
                    else:
                        st.caption("Vector index not loaded")
            else:
                st.caption(f"Retriever type: {retriever_type}")

            # Metadata if available
            metadata = stats_data.get("metadata", {})
            if metadata:
                st.markdown("##### 📋 Index Metadata")
                with st.expander("View metadata", expanded=False):
                    st.json(metadata)

        else:
            # Unexpected format, show raw data
            st.warning("⚠️ Unexpected index stats format")
            with st.expander("View raw data", expanded=False):
                st.json(stats_data)

        # Response time (with null safety)
        response_time = index_result.get("response_time_ms")
        if response_time is not None:
            st.caption(f"Response time: {float(response_time):.0f}ms")

    else:
        st.error(f"❌ Index Stats Failed: {index_result.get('error', 'Unknown error')}")

    # Component Status - API-based checks (no local imports)
    st.markdown("---")
    st.markdown("#### 🔧 Component Status (Backend)")
    st.caption("Status based on backend API responses - reflects actual runtime state")

    col1, col2, col3 = st.columns(3)

    with col1:
        # RAG Retriever - based on index stats (supports both FAISS and Weaviate)
        if index_result.get("success"):
            stats_data = index_result.get("data", {})
            retriever_type = stats_data.get("retriever_type", "unknown")

            # Check if retriever is functional
            retriever_ready = False
            retriever_info = ""

            if retriever_type == "weaviate":
                # Weaviate mode
                weaviate_stats = stats_data.get("weaviate", {})
                retriever_ready = weaviate_stats.get("loaded", False)
                retriever_info = "Weaviate"
            elif (
                retriever_type == "hybrid_modern"
                or retriever_type == "hybrid_with_tags"
            ):
                # Modern Hybrid mode (Weaviate + OpenSearch + optional tags)
                weaviate_stats = stats_data.get("weaviate", {})
                opensearch_stats = stats_data.get("opensearch", {})
                weaviate_ready = weaviate_stats.get("status") == "healthy"
                opensearch_ready = opensearch_stats.get("num_documents", 0) > 0
                retriever_ready = weaviate_ready or opensearch_ready

                # Check for tags component
                tags_info = ""
                if retriever_type == "hybrid_with_tags":
                    tags_stats = stats_data.get("components", {}).get("tags", {})
                    if tags_stats and tags_stats.get("status") != "disabled":
                        tags_ready = tags_stats.get("status") == "healthy"
                        tags_count = tags_stats.get("doc_count", 0)
                        tags_info = (
                            f" | Tags: {'✓' if tags_ready else '✗'} ({tags_count})"
                        )

                retriever_info = f"Weaviate: {'✓' if weaviate_ready else '✗'} | OpenSearch: {'✓' if opensearch_ready else '✗'}{tags_info}"
            elif retriever_type == "hybrid_legacy" or retriever_type == "faiss":
                # FAISS mode (legacy)
                has_bm25 = False
                has_faiss = False

                if "bm25_documents" in stats_data:
                    has_bm25 = stats_data.get("bm25_documents", 0) > 0
                    has_faiss = stats_data.get("faiss_documents", 0) > 0
                elif "bm25" in stats_data:
                    has_bm25 = stats_data.get("bm25", {}).get("loaded", False)
                    has_faiss = stats_data.get("faiss", {}).get("loaded", False)

                retriever_ready = has_bm25 or has_faiss
                retriever_info = f"BM25: {'✓' if has_bm25 else '✗'} | Vector: {'✓' if has_faiss else '✗'}"

            if retriever_ready:
                st.success("✅ RAG Retriever")
                st.caption(retriever_info)
            else:
                st.warning("⚠️ RAG Retriever")
                st.caption("Not loaded")
        else:
            st.error("❌ RAG Retriever")
            st.caption("Cannot verify")

    with col2:
        # RAG Generator - based on LLM provider status
        if health_result.get("success"):
            health_data = health_result.get("data", {})
            llm_ready = health_data.get("llm_provider_ready", False)

            if llm_ready:
                st.success("✅ RAG Generator")
                provider = health_data.get("llm_provider", "unknown")
                st.caption(f"LLM: {provider}")
            else:
                st.warning("⚠️ RAG Generator")
                st.caption("LLM not ready")
        else:
            st.error("❌ RAG Generator")
            st.caption("Cannot verify")

    with col3:
        # Backend API Overall
        if health_result.get("success") and index_result.get("success"):
            st.success("✅ Backend API")
            health_data = health_result.get("data", {})
            st.caption(f"Uptime: {health_data.get('uptime_human', 'N/A')}")
        elif health_result.get("success"):
            st.warning("⚠️ Backend API")
            st.caption("Partial availability")
        else:
            st.error("❌ Backend API")
            st.caption(health_result.get("error", "Disconnected"))


def render_compact_status(api_base_url: str = None) -> Dict[str, bool]:
    """
    Render a compact version of system status (for sidebar)

    Args:
        api_base_url: API base URL

    Returns:
        Dict with status flags
    """
    if api_base_url is None:
        api_base_url = st.session_state.get("api_base_url", "http://localhost:8000")

    # Quick health check
    health_result = fetch_health_status(api_base_url, timeout=2)
    index_result = fetch_index_stats(api_base_url, timeout=2)

    status = {
        "api_healthy": health_result.get("success", False),
        "indices_loaded": False,
        "llm_ready": False,
    }

    if health_result.get("success"):
        health_data = health_result.get("data", {})
        status["llm_ready"] = health_data.get("llm_provider_ready", False)

    if index_result.get("success"):
        stats_data = index_result.get("data", {})
        retriever_type = stats_data.get("retriever_type", "unknown")

        # Check if indices are loaded - support all retriever modes
        if retriever_type == "hybrid_modern":
            # Modern Hybrid mode (Weaviate + OpenSearch)
            weaviate_stats = stats_data.get("weaviate", {})
            opensearch_stats = stats_data.get("opensearch", {})
            weaviate_ready = weaviate_stats.get("status") == "healthy"
            opensearch_ready = opensearch_stats.get("num_documents", 0) > 0
            status["indices_loaded"] = weaviate_ready or opensearch_ready
        elif retriever_type == "weaviate":
            # Weaviate mode (Phase 4)
            weaviate_stats = stats_data.get("weaviate", {})
            status["indices_loaded"] = weaviate_stats.get("loaded", False)
        elif retriever_type == "hybrid_legacy" or "bm25_documents" in stats_data:
            # Legacy format
            status["indices_loaded"] = stats_data.get("bm25_documents", 0) > 0
        elif "bm25" in stats_data:
            # FAISS mode
            status["indices_loaded"] = stats_data.get("bm25", {}).get("loaded", False)

    # Display compact status
    if status["api_healthy"]:
        st.success("✅ API Connected")
    else:
        st.error("❌ API Disconnected")

    if status["indices_loaded"]:
        st.success("✅ Indices Loaded")
    else:
        st.warning("⚠️ Indices Not Loaded")

    if status["llm_ready"]:
        st.success("✅ LLM Ready")
    else:
        st.warning("⚠️ LLM Not Ready")

    return status


if __name__ == "__main__":
    # Test the component
    st.set_page_config(page_title="System Status Test", layout="wide")
    st.title("System Status Component Test")

    # Test with default localhost
    api_url = st.text_input("API Base URL", value="http://localhost:8000")

    # Render the component
    render_system_status(api_url)
