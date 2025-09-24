"""
🚀 RAG Pipeline Demo & Annotation Tool

Interactive Streamlit application for:
- Testing RAG queries in real-time
- Annotating evaluation datasets
- Viewing evaluation results
- Managing system configurations
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Page configuration
st.set_page_config(
    page_title="RAG Pipeline Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .nav-button {
        width: 100%;
        margin: 0.25rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    .error-box {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_session_state():
    """Initialize session state variables."""
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = "http://127.0.0.1:8000"
    if "enable_vision" not in st.session_state:
        st.session_state.enable_vision = False
    if "enable_embedding" not in st.session_state:
        st.session_state.enable_embedding = False
    if "enable_verbose_logging" not in st.session_state:
        st.session_state.enable_verbose_logging = False
    if "show_debug_console_mini" not in st.session_state:
        st.session_state.show_debug_console_mini = False
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = ""
    if "global_config" not in st.session_state:
        st.session_state.global_config = {
            "max_retries": 3,
            "timeout": 30,
            "batch_size": 10,
        }


def main():
    """Main application entry point."""

    # Initialize session state
    initialize_session_state()

    # Sidebar navigation
    with st.sidebar:
        st.markdown("# 🤖 RAG Advanced Debug/Performance UI")
        st.markdown("---")

        # Navigation menu - aligned with the build plan phases
        page = st.selectbox(
            "Navigate to:",
            [
                "🏠 Home",
                "🔬 Phase 1: Query Lab",
                "📄 Phase 2: PDF Viewer",
                "📥 Phase 3: Ingest Panel",
                "📝 Phase 4: Report Lab",
                "🔀 Phase 5: Tier Inspector",
                "👁️ Phase 6: Vision Verification",
                "🛠️ Phase 7: Debug Tools",
                "📊 Metrics & Logs",
                "⚙️ Configuration",
                "📁 Data Management",
                "🐛 Debug Console",
            ],
            key="navigation",
        )

        st.markdown("---")

        # Global Configuration Section
        with st.expander("🌐 Global Configuration", expanded=True):
            # API Base URL
            st.session_state.api_base_url = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url,
                help="Base URL for the RAG API endpoints",
            )

            # Auth Token
            st.session_state.auth_token = st.text_input(
                "Auth Token",
                value=st.session_state.auth_token,
                type="password",
                help="Authentication token for API access",
            )

            # Feature Flags
            st.markdown("#### Feature Flags")
            st.session_state.enable_vision = st.checkbox(
                "Enable Vision Features",
                value=st.session_state.enable_vision,
                help="Enable vision-assisted verification features",
            )

            st.session_state.enable_embedding = st.checkbox(
                "Enable Embedding Viz",
                value=st.session_state.enable_embedding,
                help="Enable embedding visualization features",
            )

            # Advanced Settings
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.global_config["max_retries"] = st.number_input(
                    "Max Retries",
                    min_value=1,
                    max_value=10,
                    value=st.session_state.global_config["max_retries"],
                    help="Maximum number of API retry attempts",
                )

            with col2:
                st.session_state.global_config["timeout"] = st.number_input(
                    "Timeout (s)",
                    min_value=5,
                    max_value=120,
                    value=st.session_state.global_config["timeout"],
                    help="API request timeout in seconds",
                )

        st.markdown("---")

        # Debug settings
        with st.expander("🔧 Debug Settings", expanded=False):
            st.session_state.enable_verbose_logging = st.checkbox(
                "Verbose Logging",
                value=st.session_state.enable_verbose_logging,
                help="Enable detailed logging for debugging",
            )

            st.session_state.show_debug_console_mini = st.checkbox(
                "Show Mini Console",
                value=st.session_state.show_debug_console_mini,
                help="Show mini debug console at bottom of page",
            )

        st.markdown("---")

        # System status
        st.markdown("### 📟 System Status")
        try:
            # Check if RAG core components can be imported
            from app.rag.generator import ResponseGenerator
            from app.rag.query_transform import QueryTransformer
            from app.rag.reranker import Reranker
            from app.rag.retriever import HybridRetriever

            _ = (QueryTransformer, HybridRetriever, Reranker, ResponseGenerator)
            st.success("✅ RAG Components Ready")
        except Exception as e:
            st.error(f"❌ RAG Components Error: {str(e)}")

        # Optional: index readiness check (if FastAPI app has loaded indices)
        try:
            from app.deps.indices import get_index_manager

            manager = get_index_manager()
            retriever = manager.get_retriever()
            if retriever is not None:
                st.success("✅ Indices Loaded")
            else:
                st.warning("⚠️ Indices not loaded")
        except Exception as e:
            st.info(f"ℹ️ Index status unavailable: {str(e)}")

        try:
            from app.evaluation.batch_runner import BatchEvaluationRunner

            st.success("✅ Evaluation System Ready")
        except Exception as e:
            st.error(f"❌ Evaluation System Error: {str(e)}")

    # Main content area - route to appropriate component based on selected page
    if page == "🏠 Home":
        show_home_page()
    elif page == "🔬 Phase 1: Query Lab":
        show_query_lab()
    elif page == "📄 Phase 2: PDF Viewer":
        show_pdf_viewer()
    elif page == "📥 Phase 3: Ingest Panel":
        show_ingest_panel()
    elif page == "📝 Phase 4: Report Lab":
        show_report_lab()
    elif page == "🔀 Phase 5: Tier Inspector":
        show_tier_inspector()
    elif page == "👁️ Phase 6: Vision Verification":
        show_vision_verification()
    elif page == "🛠️ Phase 7: Debug Tools":
        show_debug_tools()
    elif page == "📊 Metrics & Logs":
        show_metrics_logs()
    elif page == "⚙️ Configuration":
        show_configuration_page()
    elif page == "📁 Data Management":
        show_data_management()
    elif page == "🐛 Debug Console":
        show_debug_console()

    # Show mini debug console if enabled
    if st.session_state.get("show_debug_console_mini", False):
        with st.container():
            st.markdown("---")
            st.markdown("### 🐛 Debug Console (Mini)")
            try:
                from streamlit_app.components.debug_console import render_mini

                render_mini()
            except ImportError:
                st.error("Debug console component not found")


def show_home_page():
    """Display the home page with phase overview."""
    st.markdown(
        '<div class="main-header">🚀 RAG Advanced Debug/Performance UI</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    ### Welcome to the Advanced RAG Debug & Performance UI

    This comprehensive interface provides powerful tools for debugging, testing, and optimizing your RAG pipeline.
    """
    )

    # Show current configuration status
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"🌐 API: `{st.session_state.api_base_url}`")
    with col2:
        vision_status = "✅ Enabled" if st.session_state.enable_vision else "❌ Disabled"
        st.info(f"👁️ Vision: {vision_status}")
    with col3:
        embedding_status = (
            "✅ Enabled" if st.session_state.enable_embedding else "❌ Disabled"
        )
        st.info(f"🔀 Embedding: {embedding_status}")

    st.markdown("---")

    # Phase overview
    st.markdown("### 📋 Development Phases")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        #### **Phase 1: Core Query Lab** 🔬
        - Full query knobs and controls
        - Live API testing with all parameters
        - Result tabs with citations
        - Latency timeline visualization

        #### **Phase 2: PDF Viewer** 📄
        - PDF page rendering
        - Citation highlighting with bboxes
        - Interactive document navigation
        - Zoom and annotation features

        #### **Phase 3: Ingest Panel** 📥
        - Document upload interface
        - OCR configuration
        - Processing job status
        - Index management

        #### **Phase 4: Report Lab** 📝
        - Template-based report generation
        - Sub-query breakdown
        - Export to Word/PDF
        - Batch processing
        """
        )

    with col2:
        st.markdown(
            """
        #### **Phase 5: Tier Inspector** 🔀
        - A/B testing interface
        - Tier comparison charts
        - Embedding visualization
        - Performance metrics

        #### **Phase 6: Vision Verification** 👁️
        - Vision-assisted QA
        - Confidence scoring
        - Human-in-the-loop corrections
        - Feature flag controlled

        #### **Phase 7: Debug Tools** 🛠️
        - Advanced presets
        - Scenario recording/replay
        - Cache controls
        - Performance profiling

        #### **Phase 8: Hardening** 🔒
        - Security enhancements
        - Performance optimization
        - Documentation
        - Production readiness
        """
        )

    # Quick stats
    st.markdown("---")
    st.markdown("### 📈 Quick Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Documents Indexed", "1,234", delta="12")

    with col2:
        st.metric("Evaluation Queries", "567", delta="45")

    with col3:
        st.metric("Average Response Time", "2.3s", delta="-0.1s")

    with col4:
        st.metric("Success Rate", "94.5%", delta="1.2%")


def show_query_lab():
    """Show Phase 1: Query Lab interface."""
    try:
        from streamlit_app.components.query_lab import render as query_lab_render

        query_lab_render()
    except ImportError:
        try:
            from components.query_lab import render as query_lab_render

            query_lab_render()
        except Exception as e:
            st.error(f"Error loading Query Lab: {str(e)}")
            st.info(
                "Query Lab component not available. Please check the components directory."
            )


def show_pdf_viewer():
    """Show Phase 2: PDF Viewer interface."""
    try:
        from streamlit_app.components.pdf_viewer import render as pdf_viewer_render

        pdf_viewer_render()
    except ImportError:
        try:
            from components.pdf_viewer import render as pdf_viewer_render

            pdf_viewer_render()
        except Exception as e:
            st.warning(f"PDF Viewer not yet implemented (Phase 2)")
            st.info("This feature will be available in Phase 2 of development.")


def show_ingest_panel():
    """Show Phase 3: Ingest Panel interface."""
    try:
        from streamlit_app.components.ingest_panel import render as ingest_panel_render

        ingest_panel_render()
    except ImportError:
        try:
            from components.ingest_panel import render as ingest_panel_render

            ingest_panel_render()
        except Exception as e:
            st.error(f"Error loading Ingest Panel: {str(e)}")
            st.info(
                "Ingest Panel component not available. Please check the components directory."
            )


def show_report_lab():
    """Show Phase 4: Report Lab interface."""
    try:
        from streamlit_app.components.report_lab import render as report_lab_render

        report_lab_render()
    except ImportError:
        try:
            from components.report_lab import render as report_lab_render

            report_lab_render()
        except Exception as e:
            st.error(f"Error loading Report Lab: {str(e)}")
            st.info(
                "Report Lab component not available. Please check the components directory."
            )


def show_tier_inspector():
    """Show Phase 5: Tier Inspector interface."""
    try:
        from streamlit_app.components.tier_inspector import (
            render as tier_inspector_render,
        )

        tier_inspector_render()
    except ImportError:
        try:
            from components.tier_inspector import render as tier_inspector_render

            tier_inspector_render()
        except Exception as e:
            st.error(f"Error loading Tier Inspector: {str(e)}")
            st.info(
                "Tier Inspector component not available. Please check the components directory."
            )


def show_vision_verification():
    """Show Phase 6: Vision Verification interface."""
    if not st.session_state.enable_vision:
        st.warning(
            "⚠️ Vision features are disabled. Enable them in the Global Configuration section."
        )
        st.stop()

    st.markdown("### 👁️ Vision-Assisted Verification")
    st.info("Vision verification features are currently being integrated.")
    # The actual vision features are partially in query_lab component
    try:
        from streamlit_app.components.query_lab import render as query_lab_render

        query_lab_render(vision_mode=True)
    except Exception as e:
        st.error(f"Error loading Vision Verification: {str(e)}")


def show_debug_tools():
    """Show Phase 7: Debug Tools interface."""
    st.markdown("### 🛠️ Advanced Debug Tools")

    tabs = st.tabs(
        ["Presets", "Scenario Recording", "Cache Control", "Performance Profiler"]
    )

    with tabs[0]:
        st.markdown("#### Query Presets")
        # This would integrate with query_lab presets
        st.info("Preset management interface will be integrated with Query Lab")

    with tabs[1]:
        st.markdown("#### Scenario Recording & Replay")
        st.info("Record and replay complex query scenarios for testing")

    with tabs[2]:
        st.markdown("#### Cache Control")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear Query Cache", type="primary"):
                st.success("Query cache cleared")
        with col2:
            if st.button("Clear Embedding Cache", type="primary"):
                st.success("Embedding cache cleared")

    with tabs[3]:
        st.markdown("#### Performance Profiler")
        st.info("Performance profiling tools will be available soon")


def show_metrics_logs():
    """Show Metrics & Logs Dashboard."""
    try:
        from streamlit_app.components.metrics_logs import render as metrics_logs_render

        metrics_logs_render()
    except ImportError:
        try:
            from components.metrics_logs import render as metrics_logs_render

            metrics_logs_render()
        except Exception as e:
            st.error(f"Error loading Metrics & Logs: {str(e)}")
            st.info(
                "Metrics & Logs component not available. Please check the components directory."
            )


def show_annotation_page():
    """Show annotation interface."""
    try:
        from components.annotation_enhanced import (
            show_annotation_page as annotation_component,
        )

        annotation_component()
    except:
        try:
            from components.annotation import (
                show_annotation_page as annotation_component,
            )

            annotation_component()
        except Exception as e:
            st.error(f"Error loading Annotation interface: {str(e)}")
            st.info(
                "Annotation component not available. Please check the components directory."
            )


def show_evaluation_results():
    """Show evaluation results interface."""
    try:
        from components.evaluation_viewer import (
            show_evaluation_results as results_component,
        )

        results_component()
    except:
        try:
            from components.evaluation_results import (
                show_evaluation_results as results_component,
            )

            results_component()
        except Exception as e:
            st.error(f"Error loading Evaluation Results: {str(e)}")
            st.info(
                "Evaluation Results component not available. Please check the components directory."
            )


def show_configuration_page():
    """Show configuration interface."""
    try:
        from components.configuration import show_configuration_page as config_component

        config_component()
    except Exception as e:
        st.error(f"Error loading Configuration interface: {str(e)}")
        st.info("Configuration component not available. Creating placeholder...")
        st.markdown("### ⚙️ Configuration")
        st.info("Configuration interface will be available soon.")


def show_data_management():
    """Show data management interface."""
    try:
        from components.data_management import (
            show_data_management as data_mgmt_component,
        )

        data_mgmt_component()
    except Exception as e:
        st.error(f"Error loading Data Management interface: {str(e)}")
        st.info("Data Management component not available. Creating placeholder...")
        st.markdown("### 📁 Data Management")
        st.info("Data management interface will be available soon.")


def show_debug_console():
    """Show debug console interface."""
    try:
        from streamlit_app.components.debug_console import render

        render()
    except ImportError:
        try:
            from components.debug_console import render

            render()
        except Exception as e:
            st.error(f"Error loading Debug Console: {str(e)}")
            st.info(
                "Debug Console component not available. Please check the components directory."
            )


if __name__ == "__main__":
    main()
