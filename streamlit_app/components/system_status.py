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
    Render the System Status section

    Args:
        api_base_url: API base URL (uses session state if not provided)
    """

    # Use provided URL or get from session state
    if api_base_url is None:
        api_base_url = st.session_state.get("api_base_url", "http://localhost:8000")

    st.markdown("### 📟 System Status")

    # Create refresh button
    col1, col2, col3 = st.columns([2, 1, 3])
    with col2:
        refresh = st.button("🔄 Refresh", use_container_width=True)

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
        st.caption(f"Last updated: {cache_time}")

    # Display Health Status
    st.markdown("#### 🏥 API Health")

    if health_result.get("success"):
        health_data = health_result["data"]

        # Main status
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            status = health_data.get("status", "unknown")
            if status == "healthy":
                st.success(f"✅ {status.upper()}")
            else:
                st.error(f"❌ {status.upper()}")

        with col2:
            env = health_data.get("app_env", "unknown")
            st.info(f"🌍 Env: {env}")

        with col3:
            version = health_data.get("version", "unknown")
            st.info(f"📦 v{version}")

        with col4:
            uptime = health_data.get("uptime_human", "unknown")
            st.info(f"⏱️ {uptime}")

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

        # Response time
        response_time = health_result.get("response_time_ms", 0)
        st.caption(f"Response time: {response_time:.0f}ms")
    else:
        st.error(
            f"❌ API Health Check Failed: {health_result.get('error', 'Unknown error')}"
        )

    st.markdown("---")

    # Display Index Statistics
    st.markdown("#### 📊 Index Statistics")

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

        elif "bm25" in stats_data or "faiss" in stats_data:
            # Using index manager format
            col1, col2 = st.columns(2)

            # BM25 Stats
            with col1:
                bm25_stats = stats_data.get("bm25", {})
                if bm25_stats.get("loaded"):
                    st.success("✅ BM25 Index Loaded")
                    doc_count = bm25_stats.get("doc_count", 0)
                    chunk_count = bm25_stats.get("chunk_count", 0)
                    st.metric("Documents", f"{doc_count:,}")
                    st.metric("Chunks", f"{chunk_count:,}")
                else:
                    st.warning("⚠️ BM25 Index Not Loaded")
                    st.caption("No BM25 index available")

            # FAISS Stats
            with col2:
                faiss_stats = stats_data.get("faiss", {})
                if faiss_stats.get("loaded"):
                    st.success("✅ FAISS Index Loaded")
                    vector_count = faiss_stats.get("vector_count", 0)
                    dimension = faiss_stats.get("dimension", 0)
                    st.metric("Vectors", f"{vector_count:,}")
                    st.metric("Dimension", dimension)
                else:
                    st.warning("⚠️ FAISS Index Not Loaded")
                    st.caption("No FAISS index available")

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

        # Response time
        response_time = index_result.get("response_time_ms", 0)
        st.caption(f"Response time: {response_time:.0f}ms")

    else:
        st.error(f"❌ Index Stats Failed: {index_result.get('error', 'Unknown error')}")

    # Component Status - API-based checks (no local imports)
    st.markdown("---")
    st.markdown("#### 🔧 Component Status (Backend)")
    st.caption("Status based on backend API responses - reflects actual runtime state")

    col1, col2, col3 = st.columns(3)

    with col1:
        # RAG Retriever - based on index stats
        if index_result.get("success"):
            stats_data = index_result.get("data", {})
            # Check if retriever is functional by verifying indices
            has_bm25 = False
            has_faiss = False

            if "bm25_documents" in stats_data:
                has_bm25 = stats_data.get("bm25_documents", 0) > 0
                has_faiss = stats_data.get("faiss_documents", 0) > 0
            elif "bm25" in stats_data:
                has_bm25 = stats_data.get("bm25", {}).get("loaded", False)
                has_faiss = stats_data.get("faiss", {}).get("loaded", False)

            if has_bm25 or has_faiss:
                st.success("✅ RAG Retriever")
                st.caption(
                    f"BM25: {'✓' if has_bm25 else '✗'} | FAISS: {'✓' if has_faiss else '✗'}"
                )
            else:
                st.warning("⚠️ RAG Retriever")
                st.caption("No indices loaded")
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
        # Check if indices are loaded
        if "bm25_documents" in stats_data:
            status["indices_loaded"] = stats_data.get("bm25_documents", 0) > 0
        elif "bm25" in stats_data:
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
