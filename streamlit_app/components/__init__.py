"""
Streamlit UI components for the RAG Pipeline Demo & Annotation Tool.

This package contains all the UI components for the interactive Streamlit application:
- rag_demo: Interactive RAG testing interface
- annotation: QA dataset creation and management
- evaluation_results: Performance analysis and visualization
- configuration: System settings and parameter management
- data_management: Import/export and data utilities
"""

__version__ = "1.0.0"

# Export all components for easier imports
__all__ = [
    "dashboard",
    "query_lab",
    "report_lab",
    "ingest_panel",
    "tier_inspector",
    "metrics_logs",
    "debug_console",
    "query_lab_enhanced",
]
