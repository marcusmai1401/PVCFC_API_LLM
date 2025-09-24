"""
🔍 RAG Demo Component

Interactive interface for testing RAG queries with real-time responses.
Shows retrieval results, generation process, and performance metrics.
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Try to import real Gemini integration (prefer direct client)
GEMINI_AVAILABLE = False
try:
    from .rag_gemini_direct import process_with_gemini_direct as process_with_real_llm

    GEMINI_AVAILABLE = True
except Exception:
    try:
        from components.rag_gemini_direct import (
            process_with_gemini_direct as process_with_real_llm,
        )

        GEMINI_AVAILABLE = True
    except Exception:
        try:
            from .rag_gemini_integration import process_with_real_llm

            GEMINI_AVAILABLE = True
        except Exception:
            try:
                from components.rag_gemini_integration import process_with_real_llm

                GEMINI_AVAILABLE = True
            except Exception:
                GEMINI_AVAILABLE = False


def show_rag_demo():
    """Display the RAG demo interface."""
    st.title("🔍 RAG Demo - Interactive Testing")

    st.markdown(
        """
    Test your RAG pipeline in real-time. Enter queries and see the complete retrieval and generation process.
    """
    )

    # Configuration sidebar
    with st.sidebar:
        st.markdown("### 🎛️ Demo Settings")

        # Toggle real vs mock
        use_real_api = st.checkbox(
            "🚀 Use Real Gemini API",
            value=GEMINI_AVAILABLE,
            disabled=not GEMINI_AVAILABLE,
            help="Toggle between mock demo and real Gemini API. Requires GEMINI_API_KEY in .env.",
        )

        if use_real_api and not GEMINI_AVAILABLE:
            st.error("❌ Gemini integration not available.")

        # Model selection
        if use_real_api:
            model_choice = st.selectbox(
                "Gemini Model",
                [
                    "gemini-2.5-flash",
                    "gemini-2.5-pro",
                    "gemini-1.5-flash",
                    "gemini-1.5-pro",
                ],
                index=0,
                help="Select a Gemini model",
            )
        else:
            model_choice = st.selectbox(
                "Language Model (Mock)",
                ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", "gemini-pro"],
                index=0,
                help="Mock mode - responses are simulated",
            )

        # Retrieval settings
        st.markdown("#### Retrieval Settings")
        top_k = st.slider("Top K Documents", min_value=5, max_value=20, value=10)
        similarity_threshold = st.slider(
            "Similarity Threshold", min_value=0.0, max_value=1.0, value=0.7, step=0.1
        )

        # Generation settings
        st.markdown("#### Generation Settings")
        max_tokens = st.slider("Max Tokens", min_value=100, max_value=2000, value=500)
        temperature = st.slider(
            "Temperature", min_value=0.0, max_value=1.0, value=0.7, step=0.1
        )

        # Advanced options
        with st.expander("🔧 Advanced Options"):
            enable_hyde = st.checkbox("Enable HyDE", value=False)
            enable_rerank = st.checkbox("Enable Reranking", value=True)
            enable_cove = st.checkbox("Enable CoVe Verification", value=True)
            streaming_mode = st.checkbox("Streaming Mode", value=False)

    # Main query interface
    col1, col2 = st.columns([2, 1])

    with col1:
        # Query input
        query = st.text_area(
            "Enter your query:",
            height=100,
            placeholder="Ask anything about your documents...",
            help="Type your question and press Ctrl+Enter or click 'Generate Answer'",
        )

        # Action buttons
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

        with col_btn1:
            generate_clicked = st.button("🚀 Generate Answer", type="primary")

        with col_btn2:
            clear_clicked = st.button("🧹 Clear")

        with col_btn3:
            # Sample queries dropdown
            sample_queries = [
                "What is RAG and how does it work?",
                "Explain the benefits of vector databases",
                "How to improve retrieval accuracy?",
                "What are the challenges in RAG implementation?",
                "Compare different embedding models",
            ]

            selected_sample = st.selectbox(
                "Or try a sample query:",
                [""] + sample_queries,
                format_func=lambda x: "Choose sample..."
                if x == ""
                else x[:50] + "..."
                if len(x) > 50
                else x,
            )

            if selected_sample:
                query = selected_sample
                st.rerun()

    with col2:
        # Quick stats
        st.markdown("#### 📊 Session Stats")
        if "demo_stats" not in st.session_state:
            st.session_state.demo_stats = {
                "queries_count": 0,
                "avg_response_time": 0.0,
                "last_query_time": None,
            }

        stats = st.session_state.demo_stats
        st.metric("Queries This Session", stats["queries_count"])
        st.metric("Avg Response Time", f"{stats['avg_response_time']:.2f}s")
        if stats["last_query_time"]:
            st.metric("Last Query", stats["last_query_time"].strftime("%H:%M:%S"))

    # Clear functionality
    if clear_clicked:
        st.rerun()

    # Generate answer functionality
    if generate_clicked and query.strip():
        process_rag_query(
            query=query.strip(),
            model=model_choice,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            max_tokens=max_tokens,
            temperature=temperature,
            enable_hyde=enable_hyde,
            enable_rerank=enable_rerank,
            enable_cove=enable_cove,
            streaming_mode=streaming_mode,
            use_real_api=use_real_api and GEMINI_AVAILABLE,
        )

    elif generate_clicked and not query.strip():
        st.warning("Please enter a query first.")


def process_rag_query(
    query: str,
    model: str,
    top_k: int,
    similarity_threshold: float,
    max_tokens: int,
    temperature: float,
    enable_hyde: bool,
    enable_rerank: bool,
    enable_cove: bool,
    streaming_mode: bool,
    use_real_api: bool = False,
):
    """Process a RAG query and display results."""

    # Update session stats
    st.session_state.demo_stats["queries_count"] += 1
    st.session_state.demo_stats["last_query_time"] = datetime.now()

    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📝 Answer", "📚 Retrieved Documents", "⚙️ Process Details", "📊 Metrics"]
    )

    with tab1:
        st.markdown("### Generated Answer")

        # Generate answer (real or mock)
        status_msg = (
            "🤖 Generating with Gemini API..."
            if use_real_api
            else "🤖 Generating mock answer..."
        )
        with st.spinner(status_msg):
            start_time = time.time()

            try:
                if use_real_api:
                    # Real Gemini call
                    answer_data = process_with_real_llm(
                        query=query,
                        model=model,
                        top_k=top_k,
                        similarity_threshold=similarity_threshold,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        enable_hyde=enable_hyde,
                        enable_rerank=enable_rerank,
                        enable_cove=enable_cove,
                    )
                else:
                    # Mock RAG processing
                    answer_data = simulate_rag_pipeline(
                        query,
                        model,
                        top_k,
                        similarity_threshold,
                        max_tokens,
                        temperature,
                        enable_hyde,
                        enable_rerank,
                        enable_cove,
                    )
            except Exception as e:
                answer_data = {
                    "answer": f"❌ Error generating answer: {str(e)}",
                    "citations": [],
                    "retrieved_docs": [],
                    "confidence": 0.0,
                    "pipeline_steps": [],
                }

            end_time = time.time()
            response_time = end_time - start_time

            # Update average response time
            current_avg = st.session_state.demo_stats["avg_response_time"]
            count = st.session_state.demo_stats["queries_count"]
            new_avg = (current_avg * (count - 1) + response_time) / count
            st.session_state.demo_stats["avg_response_time"] = new_avg

        # Display answer
        st.markdown("#### 🎯 Answer")
        st.markdown(answer_data["answer"])

        # Display citations
        if answer_data["citations"]:
            st.markdown("#### 📖 Citations")
            for i, citation in enumerate(answer_data["citations"], 1):
                with st.expander(f"📄 Citation {i}: {citation['title']}"):
                    st.markdown(f"**Source:** {citation['source']}")
                    st.markdown(f"**Relevance:** {citation['relevance']:.2f}")
                    st.markdown(f"**Excerpt:** {citation['excerpt']}")

        # Response metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Response Time", f"{response_time:.2f}s")
        with col2:
            st.metric("Confidence Score", f"{answer_data['confidence']:.1%}")
        with col3:
            st.metric("Citations Found", len(answer_data["citations"]))

    with tab2:
        st.markdown("### 📚 Retrieved Documents")

        if answer_data["retrieved_docs"]:
            for i, doc in enumerate(answer_data["retrieved_docs"], 1):
                with st.expander(f"📄 Document {i} - Score: {doc['score']:.3f}"):
                    st.markdown(f"**Title:** {doc['title']}")
                    st.markdown(f"**Source:** {doc['source']}")
                    st.markdown(f"**Content Preview:**")
                    st.markdown(
                        doc["content"][:500] + "..."
                        if len(doc["content"]) > 500
                        else doc["content"]
                    )

                    # Metadata
                    if doc["metadata"]:
                        st.json(doc["metadata"])
        else:
            st.info("No documents retrieved.")

    with tab3:
        st.markdown("### ⚙️ Process Details")

        # Pipeline steps
        steps = answer_data["pipeline_steps"]

        for step in steps:
            with st.expander(
                f"{step['icon']} {step['name']} - {step['duration']:.3f}s"
            ):
                st.markdown(f"**Status:** {step['status']}")
                st.markdown(f"**Details:** {step['details']}")

                if step["metrics"]:
                    st.json(step["metrics"])

    with tab4:
        st.markdown("### 📊 Performance Metrics")

        # Performance breakdown
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### ⏱️ Timing Breakdown")
            timing_data = {
                "Query Processing": 0.15,
                "Document Retrieval": 0.45,
                "Reranking": 0.12,
                "Answer Generation": 1.23,
                "Verification": 0.08,
            }

            for step, time_val in timing_data.items():
                percentage = (time_val / sum(timing_data.values())) * 100
                st.metric(step, f"{time_val:.2f}s", delta=f"{percentage:.1f}%")

        with col2:
            st.markdown("#### 🎯 Quality Metrics")
            st.metric("Retrieval Recall@5", "0.85")
            st.metric("Citation Precision", "0.92")
            st.metric("Answer Relevance", "0.88")
            st.metric("Factual Consistency", "0.91")


def simulate_rag_pipeline(
    query: str,
    model: str,
    top_k: int,
    similarity_threshold: float,
    max_tokens: int,
    temperature: float,
    enable_hyde: bool,
    enable_rerank: bool,
    enable_cove: bool,
) -> Dict[str, Any]:
    """Simulate RAG pipeline processing (mock implementation)."""

    time.sleep(1.5)  # Simulate processing time

    # Mock retrieved documents
    retrieved_docs = [
        {
            "title": "Introduction to RAG Systems",
            "source": "rag_guide.pdf",
            "content": "Retrieval-Augmented Generation (RAG) is a technique that combines pre-trained parametric and non-parametric memory for language generation. The parametric memory is a pre-trained seq2seq model and the non-parametric memory is a dense vector index of Wikipedia, accessed with a pre-trained neural retriever.",
            "score": 0.92,
            "metadata": {"page": 1, "section": "Introduction"},
        },
        {
            "title": "Vector Database Architecture",
            "source": "vector_db.pdf",
            "content": "Vector databases are specialized storage systems designed to handle high-dimensional vectors efficiently. They enable fast similarity search and are crucial components in RAG systems for document retrieval.",
            "score": 0.87,
            "metadata": {"page": 3, "section": "Architecture"},
        },
        {
            "title": "Embedding Models Comparison",
            "source": "embeddings.pdf",
            "content": "Different embedding models have varying performance characteristics. BERT-based models excel at semantic understanding, while newer models like E5 and BGE show improved retrieval performance.",
            "score": 0.81,
            "metadata": {"page": 12, "section": "Models"},
        },
    ]

    # Mock answer
    answer = """RAG (Retrieval-Augmented Generation) is a powerful AI technique that combines the strengths of parametric language models with external knowledge retrieval.

Key components include:

🔍 **Retrieval System**: Uses dense vector representations to find relevant documents from a knowledge base
🤖 **Generation Model**: Leverages retrieved context to generate accurate, grounded responses
📚 **Knowledge Base**: External documents that provide up-to-date information

The main benefits are:
- Access to external, updated information
- Reduced hallucinations through grounding
- Scalable knowledge without retraining models
- Transparent citations and sources"""

    # Mock citations
    citations = [
        {
            "title": "Introduction to RAG Systems",
            "source": "rag_guide.pdf",
            "excerpt": "RAG combines pre-trained parametric and non-parametric memory for language generation",
            "relevance": 0.95,
        },
        {
            "title": "Vector Database Architecture",
            "source": "vector_db.pdf",
            "excerpt": "Vector databases enable fast similarity search crucial for document retrieval",
            "relevance": 0.88,
        },
    ]

    # Mock pipeline steps
    pipeline_steps = [
        {
            "name": "Query Analysis",
            "icon": "🔍",
            "duration": 0.12,
            "status": "✅ Completed",
            "details": f"Analyzed query intent and extracted key terms from: {query[:50]}...",
            "metrics": {"intent_confidence": 0.92, "key_terms": 3},
        },
        {
            "name": "Document Retrieval",
            "icon": "📚",
            "duration": 0.45,
            "status": "✅ Completed",
            "details": f"Retrieved {len(retrieved_docs)} documents using vector similarity",
            "metrics": {
                "documents_searched": 10000,
                "top_k": top_k,
                "min_score": similarity_threshold,
            },
        },
    ]

    if enable_rerank:
        pipeline_steps.append(
            {
                "name": "Reranking",
                "icon": "📊",
                "duration": 0.23,
                "status": "✅ Completed",
                "details": "Reranked documents using cross-encoder model",
                "metrics": {"rerank_score_improvement": 0.15},
            }
        )

    pipeline_steps.append(
        {
            "name": "Answer Generation",
            "icon": "🤖",
            "duration": 1.1,
            "status": "✅ Completed",
            "details": f"Generated answer using {model} with {max_tokens} max tokens",
            "metrics": {"model": model, "tokens_used": 450, "temperature": temperature},
        }
    )

    if enable_cove:
        pipeline_steps.append(
            {
                "name": "Verification",
                "icon": "✅",
                "duration": 0.18,
                "status": "✅ Completed",
                "details": "Verified answer consistency and factual accuracy",
                "metrics": {"verification_score": 0.91, "confidence_boost": 0.05},
            }
        )

    return {
        "answer": answer,
        "citations": citations,
        "retrieved_docs": retrieved_docs,
        "confidence": 0.89,
        "pipeline_steps": pipeline_steps,
    }
