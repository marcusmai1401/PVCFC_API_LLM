"""
🔍 RAG Demo Component - Fixed Version

Interactive interface for testing RAG queries with real-time responses.
Shows retrieval results, generation process, and performance metrics.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# Add project root to path safely
try:
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except:
    pass

# Try to import real Gemini integration
try:
    from .rag_gemini_direct import process_with_gemini_direct as process_with_real_llm

    GEMINI_AVAILABLE = True
except ImportError:
    try:
        from .rag_gemini_integration import process_with_real_llm

        GEMINI_AVAILABLE = True
    except ImportError:
        GEMINI_AVAILABLE = False


def show_rag_demo():
    """Display the RAG demo interface."""
    st.title("🔍 RAG Demo - Interactive Testing")

    st.markdown(
        """
    Test your RAG pipeline in real-time. Enter queries and see the complete retrieval and generation process.
    """
    )

    # Initialize session state
    if "demo_stats" not in st.session_state:
        st.session_state.demo_stats = {
            "queries_count": 0,
            "avg_response_time": 0.0,
            "last_query_time": None,
        }

    if "current_query" not in st.session_state:
        st.session_state.current_query = ""

    # Configuration sidebar
    with st.sidebar:
        st.markdown("### 🎛️ Demo Settings")

        # Add toggle for real API vs mock
        use_real_api = st.checkbox(
            "🚀 Use Real Gemini API",
            value=GEMINI_AVAILABLE,
            disabled=not GEMINI_AVAILABLE,
            help="Toggle between mock demo and real Gemini API. Requires GEMINI_API_KEY in .env file.",
        )

        if use_real_api and not GEMINI_AVAILABLE:
            st.error("❌ Gemini integration not available. Check your setup.")

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
                help="Select which Gemini model to use",
            )
        else:
            model_choice = st.selectbox(
                "Language Model (Mock)",
                ["gemini-pro", "gpt-4", "gpt-3.5-turbo", "claude-3-sonnet"],
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
            enable_hyde = st.checkbox("Enable HyDE", value=True)
            enable_rerank = st.checkbox("Enable Reranking", value=True)
            enable_cove = st.checkbox("Enable CoVe Verification", value=True)
            streaming_mode = st.checkbox("Streaming Mode", value=False)

    # Main query interface
    col1, col2 = st.columns([2, 1])

    with col1:
        # Sample queries dropdown FIRST (so it can update the text area)
        sample_queries = [
            "",  # Empty option
            "What is RAG and how does it work?",
            "Explain the benefits of vector databases",
            "How to improve retrieval accuracy?",
            "What are the challenges in RAG implementation?",
            "Compare different embedding models",
        ]

        selected_sample = st.selectbox(
            "Or try a sample query:",
            sample_queries,
            format_func=lambda x: "Choose sample..."
            if x == ""
            else x[:50] + "..."
            if len(x) > 50
            else x,
        )

        # Update query if sample selected
        if selected_sample:
            st.session_state.current_query = selected_sample

        # Query input
        query = st.text_area(
            "Enter your query:",
            value=st.session_state.current_query,
            height=100,
            placeholder="Ask anything about your documents...",
            help="Type your question and click 'Generate Answer'",
            key="query_input",
        )

        # Update session state when query changes
        if query != st.session_state.current_query:
            st.session_state.current_query = query

        # Action buttons
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            generate_clicked = st.button(
                "🚀 Generate Answer", type="primary", use_container_width=True
            )

        with col_btn2:
            if st.button("🧹 Clear", use_container_width=True):
                st.session_state.current_query = ""
                st.rerun()

    with col2:
        # Quick stats
        st.markdown("#### 📊 Session Stats")
        stats = st.session_state.demo_stats
        st.metric("Queries This Session", stats["queries_count"])
        st.metric("Avg Response Time", f"{stats['avg_response_time']:.2f}s")
        if stats["last_query_time"]:
            st.metric("Last Query", stats["last_query_time"].strftime("%H:%M:%S"))

    # Process query when button clicked
    if generate_clicked:
        if query and query.strip():
            with st.container():
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
        else:
            st.warning("⚠️ Please enter a query first!")


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

    # Create container for results
    result_container = st.container()

    with result_container:
        # Show processing status
        status_msg = (
            "🤖 Generating answer with Gemini API..."
            if use_real_api
            else "🤖 Generating mock answer..."
        )
        with st.spinner(status_msg):
            start_time = time.time()

            # Process with real API or mock
            try:
                if use_real_api:
                    # Use real Gemini API
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
                    # Use mock simulation
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

                end_time = time.time()
                response_time = end_time - start_time

                # Update average response time
                current_avg = st.session_state.demo_stats["avg_response_time"]
                count = st.session_state.demo_stats["queries_count"]
                new_avg = (
                    (current_avg * (count - 1) + response_time) / count
                    if count > 0
                    else response_time
                )
                st.session_state.demo_stats["avg_response_time"] = new_avg

            except Exception as e:
                st.error(f"❌ Error processing query: {str(e)}")
                return

        # Display results in tabs
        tab1, tab2, tab3, tab4 = st.tabs(
            ["📝 Answer", "📚 Retrieved Documents", "⚙️ Process Details", "📊 Metrics"]
        )

        with tab1:
            display_answer(answer_data, response_time)

        with tab2:
            display_retrieved_docs(answer_data)

        with tab3:
            display_process_details(answer_data)

        with tab4:
            display_metrics(answer_data, response_time)


def display_answer(answer_data: Dict[str, Any], response_time: float):
    """Display the generated answer."""
    st.markdown("### Generated Answer")

    # Display answer
    st.markdown("#### 🎯 Answer")
    st.info(answer_data["answer"])

    # Display citations
    if answer_data.get("citations"):
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
        st.metric("Citations Found", len(answer_data.get("citations", [])))


def display_retrieved_docs(answer_data: Dict[str, Any]):
    """Display retrieved documents."""
    st.markdown("### 📚 Retrieved Documents")

    if answer_data.get("retrieved_docs"):
        for i, doc in enumerate(answer_data["retrieved_docs"], 1):
            with st.expander(f"📄 Document {i} - Score: {doc['score']:.3f}"):
                st.markdown(f"**Title:** {doc['title']}")
                st.markdown(f"**Source:** {doc['source']}")
                st.markdown(f"**Content Preview:**")
                st.text(
                    doc["content"][:500] + "..."
                    if len(doc["content"]) > 500
                    else doc["content"]
                )

                # Metadata
                if doc.get("metadata"):
                    st.json(doc["metadata"])
    else:
        st.info("No documents retrieved.")


def display_process_details(answer_data: Dict[str, Any]):
    """Display pipeline process details."""
    st.markdown("### ⚙️ Process Details")

    # Pipeline steps
    steps = answer_data.get("pipeline_steps", [])

    for step in steps:
        with st.expander(f"{step['icon']} {step['name']} - {step['duration']:.3f}s"):
            st.markdown(f"**Status:** {step['status']}")
            st.markdown(f"**Details:** {step['details']}")

            if step.get("metrics"):
                st.json(step["metrics"])


def display_metrics(answer_data: Dict[str, Any], response_time: float):
    """Display performance metrics."""
    st.markdown("### 📊 Performance Metrics")

    # Performance breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ⏱️ Timing Breakdown")
        timing_data = {
            "Query Processing": 0.15,
            "Document Retrieval": 0.45,
            "Reranking": 0.12,
            "Answer Generation": response_time - 0.8,
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

    # Simulate processing time
    time.sleep(1.5)

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

    # Generate answer based on query
    if "RAG" in query.upper():
        answer = """RAG (Retrieval-Augmented Generation) is a powerful AI technique that combines the strengths of parametric language models with external knowledge retrieval.

Key components include:
- 🔍 **Retrieval System**: Uses dense vector representations to find relevant documents from a knowledge base
- 🤖 **Generation Model**: Leverages retrieved context to generate accurate, grounded responses
- 📚 **Knowledge Base**: External documents that provide up-to-date information

The main benefits are:
- Access to external, updated information
- Reduced hallucinations through grounding
- Scalable knowledge without retraining models
- Transparent citations and sources"""
    else:
        answer = f"""Based on your query about "{query[:50]}...", here's what I found:

This is a simulated response demonstrating how the RAG system would process your question. In a production environment, the system would:

1. Analyze your query to understand the intent
2. Retrieve relevant documents from the knowledge base
3. Generate a comprehensive answer based on the retrieved context
4. Provide citations for transparency

The answer would be specifically tailored to your question, incorporating information from multiple sources to provide accurate and helpful information."""

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
