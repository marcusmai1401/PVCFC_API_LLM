"""
Debug version of the Streamlit app to identify issues.
"""

import sys
import traceback
from pathlib import Path

import streamlit as st

# Basic configuration
st.set_page_config(page_title="RAG Pipeline Demo - Debug", page_icon="🔧", layout="wide")

st.title("🔧 Debug Mode - Checking Issues")

# Check Python version
st.write(f"Python version: {sys.version}")

# Check Streamlit version
try:
    import streamlit

    st.write(f"Streamlit version: {streamlit.__version__}")
except Exception as e:
    st.error(f"Streamlit import error: {e}")

# Check other dependencies
dependencies = ["pandas", "plotly", "numpy"]
for dep in dependencies:
    try:
        module = __import__(dep)
        version = getattr(module, "__version__", "unknown")
        st.success(f"✅ {dep}: {version}")
    except ImportError as e:
        st.error(f"❌ {dep}: Not installed - {e}")

# Test basic session state
if "counter" not in st.session_state:
    st.session_state.counter = 0

if st.button("Test Session State"):
    st.session_state.counter += 1
    st.write(f"Counter: {st.session_state.counter}")

# Test imports
st.header("Testing Component Imports")

try:
    # Test importing main app components
    st.write("Testing component imports...")

    # Add parent directory to path
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Try importing app components
    try:
        from app.core.rag_pipeline import RAGPipeline

        st.success("✅ RAG Pipeline import successful")
    except Exception as e:
        st.warning(f"⚠️ RAG Pipeline import failed (expected): {e}")

    # Test local component imports
    components_to_test = [
        "components.rag_demo",
        "components.annotation",
        "components.evaluation_results",
        "components.configuration",
        "components.data_management",
    ]

    for component in components_to_test:
        try:
            __import__(component)
            st.success(f"✅ {component} import successful")
        except Exception as e:
            st.error(f"❌ {component} import failed: {e}")
            st.code(traceback.format_exc())

except Exception as e:
    st.error(f"Major error during testing: {e}")
    st.code(traceback.format_exc())

# Memory usage check
st.header("System Resources")
try:
    import psutil

    process = psutil.Process()
    memory_info = process.memory_info()
    st.write(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")
except ImportError:
    st.info("psutil not installed - cannot check memory usage")

st.success("Debug script completed!")
