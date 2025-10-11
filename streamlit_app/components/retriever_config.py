"""
Retriever Configuration Component - Switch between FAISS and Weaviate modes
"""
from typing import Any, Dict

import requests
import streamlit as st


def render(api_base_url: str = None):
    """
    Render retriever configuration component

    Args:
        api_base_url: Base URL for API
    """
    if api_base_url is None:
        api_base_url = st.session_state.get("api_base_url", "http://localhost:8000")

    st.header("🔍 Retriever Configuration")
    st.caption("Switch between FAISS and Weaviate retrieval modes")

    # Fetch current mode
    with st.spinner("Loading current configuration..."):
        current_config = fetch_current_mode(api_base_url)

    if not current_config:
        st.error("❌ Failed to fetch current configuration")
        st.caption("Make sure the API is running at " + api_base_url)
        return

    current_mode = current_config.get("mode", "unknown")

    # Display current mode prominently
    st.markdown("---")
    st.markdown("### 📊 Current Mode")

    col1, col2 = st.columns([1, 2])

    with col1:
        if current_mode == "weaviate":
            st.success("### 🔷 Weaviate")
            st.caption("Vector Database (Phase 4)")
        elif current_mode == "faiss":
            st.info("### 📊 FAISS")
            st.caption("Hybrid Search (Legacy)")
        else:
            st.warning(f"### ⚠️ {current_mode.upper()}")
            st.caption("Unknown mode")

    with col2:
        # Show status
        if current_mode == "weaviate":
            st.markdown(
                """
            **Active Features:**
            - ✅ Pure semantic search
            - ✅ Scalable vector database
            - ✅ Real-time updates
            - ✅ Native metadata filtering
            """
            )
        elif current_mode == "faiss":
            st.markdown(
                """
            **Active Features:**
            - ✅ Hybrid search (BM25 + Vector)
            - ✅ Fast in-memory search
            - ✅ File-based indices
            - ✅ Good for small datasets
            """
            )

    # Mode selector
    st.markdown("---")
    st.markdown("### 🔄 Switch Retrieval Mode")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 FAISS Mode")
        st.markdown(
            """
        **Hybrid BM25 + Vector Search**

        **Best for:**
        - Development & prototyping
        - Small document collections (< 10K)
        - Quick local testing
        - File-based deployment

        **Features:**
        - 🚀 Fast local search
        - 💾 File-based indices
        - 🔍 Keyword + semantic
        - ⚡ No external dependencies
        """
        )

        is_faiss_active = current_mode == "faiss"

        if is_faiss_active:
            st.success("✅ Currently Active")
        else:
            if st.button("🔄 Switch to FAISS", use_container_width=True, type="primary"):
                switch_to_mode(api_base_url, "faiss")

    with col2:
        st.markdown("#### 🔷 Weaviate Mode")
        st.markdown(
            """
        **Vector Database (Phase 4)**

        **Best for:**
        - Production deployments
        - Large document collections (> 10K)
        - Frequent data updates
        - Scalable architecture

        **Features:**
        - 🔷 Scalable vector DB
        - 🔄 Real-time CRUD
        - 🎯 Native filtering
        - 📊 Advanced search
        """
        )

        is_weaviate_active = current_mode == "weaviate"

        if is_weaviate_active:
            st.success("✅ Currently Active")
        else:
            col_btn1, col_btn2 = st.columns([3, 1])
            with col_btn1:
                if st.button(
                    "🔄 Switch to Weaviate", use_container_width=True, type="primary"
                ):
                    # Check Weaviate availability
                    if not check_weaviate_availability(api_base_url):
                        st.error(
                            """
                        ⚠️ **Weaviate is not available!**

                        Please ensure:
                        1. Weaviate Docker container is running
                        2. Collection schema is created
                        3. Data is ingested into Weaviate

                        **Setup Instructions:**
                        ```bash
                        # Start Weaviate
                        docker run -d --name weaviate \\
                          -p 8080:8080 -p 50051:50051 \\
                          semitechnologies/weaviate:latest

                        # Ingest data
                        python scripts/ingest_to_weaviate.py
                        ```

                        See `PHASE4_WEAVIATE_INTEGRATION.md` for details.
                        """
                        )
                    else:
                        switch_to_mode(api_base_url, "weaviate")

            with col_btn2:
                if st.button("ℹ️", help="View setup instructions"):
                    st.info(
                        """
                    **Weaviate Setup:**

                    1. Start Docker container
                    2. Create collection schema
                    3. Ingest documents
                    4. Switch mode
                    5. Restart API
                    """
                    )

    # Show restart instructions if needed
    if st.session_state.get("requires_restart", False):
        st.markdown("---")
        st.warning(
            """
        ### ⚠️ **API Restart Required**

        Configuration has been updated in `.env` file.

        **Please restart the API for changes to take effect:**

        ```powershell
        # Stop API: Press Ctrl+C in the API terminal

        # Restart API:
        .\\launchers\\start_api.ps1
        ```

        Then refresh this page.
        """
        )

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✅ I've restarted the API", use_container_width=True):
                st.session_state["requires_restart"] = False
                st.rerun()

        with col2:
            if st.button("🔄 Check Status", use_container_width=True):
                new_config = fetch_current_mode(api_base_url)
                if new_config:
                    new_mode = new_config.get("mode")
                    st.success(f"Current mode: {new_mode}")
                    st.session_state["requires_restart"] = False
                    st.rerun()

    # Advanced settings
    st.markdown("---")
    with st.expander("🔧 Advanced Configuration"):
        config = fetch_full_config(api_base_url)

        if config:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**🔍 Retriever Settings**")
                st.metric("Type", config.get("retriever_type", "N/A"))
                st.metric(
                    "BGE Reranking",
                    "Enabled" if config.get("enable_bge_rerank") else "Disabled",
                )
                st.metric("Rerank Top K", config.get("bge_rerank_top_k", "N/A"))
                st.metric("Rerank Level", config.get("bge_rerank_level", "N/A"))

            with col2:
                st.markdown("**🤖 LLM Settings**")
                st.metric("LLM Provider", config.get("llm_provider", "N/A"))
                st.metric("Embedding Provider", config.get("embedding_provider", "N/A"))

                if config.get("retriever_type") == "weaviate":
                    st.markdown("**🔷 Weaviate Settings**")
                    st.text(f"Host: {config.get('weaviate_host', 'N/A')}")
                    st.text(f"Port: {config.get('weaviate_port', 'N/A')}")
                    st.text(f"Collection: {config.get('weaviate_collection', 'N/A')}")


def fetch_current_mode(api_base_url: str) -> Dict[str, Any]:
    """Fetch current retriever mode from API"""
    try:
        response = requests.get(f"{api_base_url}/config/retriever-mode", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to API. Is it running?")
        return None
    except Exception as e:
        st.error(f"Failed to connect to API: {e}")
        return None


def fetch_full_config(api_base_url: str) -> Dict[str, Any]:
    """Fetch full configuration from API"""
    try:
        response = requests.get(f"{api_base_url}/config/current", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None


def check_weaviate_availability(api_base_url: str) -> bool:
    """Check if Weaviate is available and ready"""
    try:
        # Try to get health check
        response = requests.get(f"{api_base_url}/healthz", timeout=5)

        if response.status_code == 200:
            # Could add more specific Weaviate checks here
            return True
        return False
    except Exception:
        return False


def switch_to_mode(api_base_url: str, target_mode: str):
    """Switch retriever mode"""
    with st.spinner(f"Switching to {target_mode.upper()} mode..."):
        try:
            response = requests.post(
                f"{api_base_url}/config/retriever-mode",
                json={"mode": target_mode},
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()

                if result.get("success"):
                    st.success(f"✅ {result.get('message')}")

                    if result.get("requires_restart"):
                        st.session_state["requires_restart"] = True
                        st.info("📝 Configuration file updated. API restart required.")
                        st.rerun()
                    else:
                        st.info("✅ Mode switched successfully!")
                        st.rerun()
                else:
                    st.error(f"❌ Failed: {result.get('message')}")
            else:
                st.error(f"❌ API error: {response.status_code}")
                with st.expander("View error details"):
                    st.code(response.text)

        except Exception as e:
            st.error(f"❌ Failed to switch mode: {e}")
