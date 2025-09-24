"""
Test script for Query Lab component
This script tests the Query Lab with mock API responses
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import streamlit as st

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the query_lab component
from components.query_lab import (
    call_ask_api,
    create_timeline_chart,
    format_citations,
    render,
)


def create_mock_response():
    """Create a mock API response for testing"""
    return {
        "answer": """Based on the P&ID diagram, the KT06101 pump operates under the following conditions:

        - **Operating Pressure**: 10-15 bar (1.0-1.5 MPa)
        - **Temperature Range**: 20-80°C
        - **Flow Rate**: 50-100 m³/h
        - **Material**: Stainless Steel 316L

        The pump is connected to the main process line via flanged connections and includes:
        - Pressure indicators (PI-101, PI-102)
        - Temperature sensor (TI-101)
        - Flow meter (FI-101)
        - Safety relief valve set at 20 bar

        Regular maintenance is required every 2000 operating hours.""",
        "confidence": 0.92,
        "citations": [
            {
                "doc_id": "PVCFC-PID-04000-v1",
                "page": 5,
                "score": 0.95,
                "bbox": [100, 200, 500, 400],
                "text": "KT06101 pump specifications showing operating parameters...",
            },
            {
                "doc_id": "PVCFC-DATASHEET-KT06101-v2",
                "page": 12,
                "score": 0.89,
                "bbox": [150, 100, 600, 300],
                "text": "Material specification: SS316L, design pressure 25 bar...",
            },
            {
                "doc_id": "PVCFC-SOP-PUMP-v1",
                "page": 3,
                "score": 0.85,
                "text": "Maintenance schedule: Every 2000 hours or 3 months...",
            },
        ],
        "warnings": [
            "Some technical data may require verification with latest P&ID revision"
        ],
        "meta": {
            "request_id": "req-12345-abcde",
            "trace_id": "trace-67890-fghij",
            "breakdown": {
                "query_transform": 125.5,
                "bm25_retrieval": 89.3,
                "faiss_retrieval": 156.7,
                "rrf_fusion": 12.4,
                "reranking": 234.8,
                "generation": 1567.9,
                "post_processing": 45.2,
            },
            "retrieval": {
                "bm25_results": [
                    {"doc_id": "PVCFC-PID-04000-v1", "score": 0.95},
                    {"doc_id": "PVCFC-DATASHEET-KT06101-v2", "score": 0.89},
                    {"doc_id": "PVCFC-SOP-PUMP-v1", "score": 0.85},
                    {"doc_id": "PVCFC-OM-PUMP-v1", "score": 0.78},
                    {"doc_id": "PVCFC-PID-04001-v1", "score": 0.72},
                ],
                "faiss_results": [
                    {"doc_id": "PVCFC-DATASHEET-KT06101-v2", "score": 0.93},
                    {"doc_id": "PVCFC-PID-04000-v1", "score": 0.91},
                    {"doc_id": "PVCFC-SPEC-PUMP-v1", "score": 0.86},
                    {"doc_id": "PVCFC-SOP-PUMP-v1", "score": 0.82},
                    {"doc_id": "PVCFC-PID-04002-v1", "score": 0.75},
                ],
                "fused_results": [
                    {"doc_id": "PVCFC-PID-04000-v1", "score": 0.96},
                    {"doc_id": "PVCFC-DATASHEET-KT06101-v2", "score": 0.92},
                    {"doc_id": "PVCFC-SOP-PUMP-v1", "score": 0.88},
                ],
            },
            "rerank": {
                "method": "cross_encoder",
                "before": [
                    {"doc_id": "PVCFC-PID-04000-v1", "score": 0.96},
                    {"doc_id": "PVCFC-DATASHEET-KT06101-v2", "score": 0.92},
                    {"doc_id": "PVCFC-SOP-PUMP-v1", "score": 0.88},
                    {"doc_id": "PVCFC-OM-PUMP-v1", "score": 0.78},
                    {"doc_id": "PVCFC-PID-04001-v1", "score": 0.72},
                ],
                "after": [
                    {"doc_id": "PVCFC-PID-04000-v1", "score": 0.98},
                    {"doc_id": "PVCFC-DATASHEET-KT06101-v2", "score": 0.94},
                    {"doc_id": "PVCFC-SOP-PUMP-v1", "score": 0.89},
                ],
            },
            "generation": {
                "model": "gpt-4",
                "latency_ms": 1567.9,
                "total_tokens": 2456,
                "prompt_tokens": 1890,
                "completion_tokens": 566,
                "estimated_cost": 0.0234,
                "prompt_info": {
                    "system_prompt_length": 450,
                    "context_chunks": 8,
                    "total_context_tokens": 1200,
                    "user_query_tokens": 240,
                },
            },
            "vision_verify": {
                "enabled": False,
                "pages_checked": 0,
                "claims_verified": 0,
                "verification_rate": 0.0,
                "corrections": [],
            },
            "cache_hits": 2,
            "index_size": 45678,
        },
        "total_latency_ms": 2231.8,
    }


def test_query_lab():
    """Test the Query Lab component"""
    st.set_page_config(page_title="Query Lab Test", page_icon="🧪", layout="wide")

    st.title("🧪 Query Lab Component Test")
    st.caption("Testing Query Lab with mock API responses")

    # Test mode selector
    test_mode = st.sidebar.radio(
        "Test Mode", ["Live API", "Mock Response", "Error Simulation"]
    )

    if test_mode == "Mock Response":
        # Mock the API call
        with patch("components.query_lab.call_ask_api") as mock_api:
            mock_api.return_value = {"success": True, "data": create_mock_response()}

            # Render the Query Lab
            render()

    elif test_mode == "Error Simulation":
        # Test error handling
        with patch("components.query_lab.call_ask_api") as mock_api:
            mock_api.return_value = {
                "success": False,
                "error": "Connection timeout: Unable to reach API server",
            }

            # Render the Query Lab
            render()

    else:
        # Live API mode
        render()

    # Additional test utilities
    with st.sidebar:
        st.divider()
        st.subheader("Test Utilities")

        if st.button("Load Mock Response"):
            st.session_state.query_results = create_mock_response()
            st.success("Mock response loaded!")
            st.rerun()

        if st.button("Clear Results"):
            st.session_state.query_results = None
            st.success("Results cleared!")
            st.rerun()

        if st.button("Show Session State"):
            st.json(dict(st.session_state))

        # Test individual components
        st.divider()
        st.subheader("Component Tests")

        if st.button("Test Citations Formatter"):
            mock_citations = create_mock_response()["citations"]
            df = format_citations(mock_citations)
            st.dataframe(df)

        if st.button("Test Timeline Chart"):
            mock_breakdown = create_mock_response()["meta"]["breakdown"]
            fig = create_timeline_chart(mock_breakdown)
            st.plotly_chart(fig)


if __name__ == "__main__":
    test_query_lab()
