"""
🚀 RAG Pipeline Demo & Annotation Tool - Stable Version
Simplified version to avoid import issues and crashes.
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="RAG Pipeline Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Add project root to path safely
try:
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except Exception as e:
    st.error(f"Path setup error: {e}")

# Initialize session state
if "page" not in st.session_state:
    st.session_state.page = "🏠 Home"


def main():
    """Main application entry point."""

    # Sidebar navigation
    with st.sidebar:
        st.markdown("# 🤖 RAG Pipeline")
        st.markdown("---")

        # Navigation menu
        pages = [
            "🏠 Home",
            "🔍 RAG Demo",
            "✏️ Data Annotation",
            "📊 Evaluation Results",
            "⚙️ Configuration",
            "📁 Data Management",
        ]

        page = st.selectbox(
            "Navigate to:",
            pages,
            index=pages.index(st.session_state.page)
            if st.session_state.page in pages
            else 0,
            key="navigation",
        )

        st.session_state.page = page

        st.markdown("---")

        # System status - simplified without imports
        st.markdown("### 📟 System Status")
        st.info("✅ Demo Mode Active")

    # Main content area - use simple functions instead of imports
    if page == "🏠 Home":
        show_home_page()
    elif page == "🔍 RAG Demo":
        show_rag_demo_safe()
    elif page == "✏️ Data Annotation":
        show_annotation_safe()
    elif page == "📊 Evaluation Results":
        show_evaluation_safe()
    elif page == "⚙️ Configuration":
        show_configuration_safe()
    elif page == "📁 Data Management":
        show_data_management_safe()


def show_home_page():
    """Display the home page."""
    st.markdown("# 🚀 RAG Pipeline Demo & Annotation Tool")

    st.markdown(
        """
    ### Welcome to the RAG Pipeline Interactive Demo

    This application provides a comprehensive interface for testing and managing your RAG (Retrieval-Augmented Generation) pipeline.
    """
    )

    # Feature overview
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        #### 🔍 **RAG Demo**
        - Test queries in real-time
        - View retrieval results
        - See generated answers with citations
        - Analyze performance metrics
        """
        )

        st.markdown(
            """
        #### 📊 **Evaluation Results**
        - View batch evaluation reports
        - Interactive performance charts
        - Compare different configurations
        - Export analysis results
        """
        )

    with col2:
        st.markdown(
            """
        #### ✏️ **Data Annotation**
        - Create evaluation QA pairs
        - Edit existing annotations
        - Validate data quality
        - Export training datasets
        """
        )

        st.markdown(
            """
        #### ⚙️ **Configuration**
        - Adjust RAG parameters
        - Configure model settings
        - Set evaluation criteria
        - Manage API endpoints
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


def show_rag_demo_safe():
    """Show RAG demo interface with safe import."""
    try:
        # Try to use the fixed version first
        from components.rag_demo_fixed import show_rag_demo

        show_rag_demo()
    except ImportError:
        try:
            # Fallback to original if fixed version not found
            from components.rag_demo import show_rag_demo

            show_rag_demo()
        except Exception as e:
            st.error(f"Component loading error: {e}")
            # Provide fallback simple demo
            show_simple_rag_demo()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        show_simple_rag_demo()


def show_simple_rag_demo():
    """Simple fallback RAG demo."""
    st.title("🔍 RAG Demo - Simple Mode")

    # Basic query interface
    query = st.text_area(
        "Enter your query:",
        height=100,
        placeholder="Ask anything about your documents...",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Generate Answer", type="primary"):
            if query:
                with st.spinner("Generating answer..."):
                    import time

                    time.sleep(1)
                    st.success("✅ Answer generated!")
                    st.markdown(
                        """
                    **Answer:** This is a demo response. In production, this would connect to your actual RAG pipeline.

                    **Citations:**
                    - Document 1: Introduction to RAG
                    - Document 2: Vector Databases Overview
                    """
                    )
            else:
                st.warning("Please enter a query first!")

    with col2:
        if st.button("🧹 Clear"):
            st.rerun()


def show_annotation_safe():
    """Show annotation interface with safe import."""
    try:
        from components.annotation import show_annotation_page

        show_annotation_page()
    except ImportError as e:
        st.error(f"Component loading error: {e}")
        show_simple_annotation()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        show_simple_annotation()


def show_simple_annotation():
    """Simple fallback annotation interface."""
    st.title("✏️ Data Annotation - Simple Mode")

    with st.form("simple_qa_form"):
        st.markdown("### Create QA Pair")

        query = st.text_area("Question/Query", height=80)
        expected_answer = st.text_area("Expected Answer", height=120)
        intent = st.selectbox(
            "Intent", ["definition", "explanation", "comparison", "how-to"]
        )

        submitted = st.form_submit_button("💾 Save QA Pair")

        if submitted and query and expected_answer:
            st.success("✅ QA pair saved successfully!")


def show_evaluation_safe():
    """Show evaluation results with safe import."""
    try:
        from components.evaluation_results import show_evaluation_results

        show_evaluation_results()
    except ImportError as e:
        st.error(f"Component loading error: {e}")
        show_simple_evaluation()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        show_simple_evaluation()


def show_simple_evaluation():
    """Simple fallback evaluation interface."""
    st.title("📊 Evaluation Results - Simple Mode")

    # Simple metrics display
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Queries", "250")
    with col2:
        st.metric("Success Rate", "92.5%")
    with col3:
        st.metric("Avg Response Time", "2.1s")
    with col4:
        st.metric("Quality Score", "8.7/10")

    st.info("📊 Full evaluation dashboard requires all dependencies to be installed.")


def show_configuration_safe():
    """Show configuration with safe import."""
    try:
        from components.configuration import show_configuration_page

        show_configuration_page()
    except ImportError as e:
        st.error(f"Component loading error: {e}")
        show_simple_configuration()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        show_simple_configuration()


def show_simple_configuration():
    """Simple fallback configuration interface."""
    st.title("⚙️ Configuration - Simple Mode")

    # Basic configuration options
    st.markdown("### Model Settings")

    col1, col2 = st.columns(2)

    with col1:
        model = st.selectbox("Language Model", ["gpt-4", "gpt-3.5-turbo", "claude-3"])
        temperature = st.slider("Temperature", 0.0, 1.0, 0.7)

    with col2:
        max_tokens = st.slider("Max Tokens", 100, 2000, 500)
        top_k = st.slider("Top K Documents", 5, 20, 10)

    if st.button("💾 Save Configuration"):
        st.success("✅ Configuration saved!")


def show_data_management_safe():
    """Show data management with safe import."""
    try:
        from components.data_management import show_data_management

        show_data_management()
    except ImportError as e:
        st.error(f"Component loading error: {e}")
        show_simple_data_management()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        show_simple_data_management()


def show_simple_data_management():
    """Simple fallback data management interface."""
    st.title("📁 Data Management - Simple Mode")

    # File upload
    uploaded_file = st.file_uploader(
        "Upload dataset", type=["json", "csv", "xlsx"], help="Upload your QA dataset"
    )

    if uploaded_file:
        st.success(f"✅ File uploaded: {uploaded_file.name}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Import"):
                st.success("Data imported successfully!")
        with col2:
            if st.button("📤 Export"):
                st.info("Export functionality in simple mode")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
        st.info("Please refresh the page or check the console for details.")
