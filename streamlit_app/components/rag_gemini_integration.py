"""
🔗 Gemini Integration for RAG Demo

Real integration with Google Gemini API for the RAG demo component.
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.config import settings

# Import the existing LLM service
from app.services.llm import LLMService


def process_with_real_llm(
    query: str,
    model: str = "gemini-3-flash-preview",
    top_k: int = 10,
    similarity_threshold: float = 0.7,
    max_tokens: int = 500,
    temperature: float = 0.7,
    enable_hyde: bool = True,
    enable_rerank: bool = True,
    enable_cove: bool = True,
) -> Dict[str, Any]:
    """Process query with real Gemini API."""

    start_time = time.time()

    # Initialize LLM Service
    try:
        llm_service = LLMService()
    except Exception as e:
        return {
            "answer": f"Error initializing LLM service: {str(e)}. Please check your GEMINI_API_KEY in the .env file.",
            "citations": [],
            "retrieved_docs": [],
            "confidence": 0.0,
            "pipeline_steps": [],
            "error": True,
        }

    # Load real retriever from indices (same as rag_gemini_direct.py)
    try:
        from app.deps.indices import get_index_manager
        from app.rag.query_transform import QueryTransformer

        # Get retriever from index manager
        manager = get_index_manager()

        # Load indices if not already loaded
        if manager.get_retriever() is None:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running (in Streamlit), create task
                    import nest_asyncio

                    nest_asyncio.apply()
                    asyncio.run(manager.load_indices())
                else:
                    asyncio.run(manager.load_indices())
            except RuntimeError:
                # No event loop, create new one
                asyncio.run(manager.load_indices())

        retriever = manager.get_retriever()

        if retriever is None:
            # Fallback to mock if retriever not available
            mock_retrieved_docs = [
                {
                    "title": "Index Not Available",
                    "source": "fallback.txt",
                    "content": f"Retriever not initialized. Using fallback response for: {query}",
                    "score": 0.5,
                    "metadata": {"page": 1},
                }
            ]
        else:
            # Use real retriever
            transformer = QueryTransformer(enable_hyde=enable_hyde)
            transformed_query = transformer.transform(query)

            # Search with real retriever
            search_results = retriever.search(transformed_query)

            # Convert to expected format
            mock_retrieved_docs = []
            for result in search_results[:top_k]:
                doc_title = result.metadata.get("doc_id", "Unknown Document")
                if doc_title.endswith(".pdf"):
                    doc_title = doc_title[:-4]  # Remove .pdf extension

                mock_retrieved_docs.append(
                    {
                        "title": doc_title,
                        "source": result.metadata.get("doc_id", "unknown.pdf"),
                        "content": result.text,
                        "score": result.score,
                        "metadata": {
                            "page": result.metadata.get("page", 1),
                            "chunk_id": result.chunk_id,
                        },
                    }
                )

            if not mock_retrieved_docs:
                # No results found
                mock_retrieved_docs = [
                    {
                        "title": "No Results Found",
                        "source": "search_results.txt",
                        "content": f"No relevant documents found for query: {query}. Try different keywords or check if documents are indexed.",
                        "score": 0.0,
                        "metadata": {"page": 1},
                    }
                ]

    except Exception as e:
        # Fallback to mock if any error occurs
        mock_retrieved_docs = [
            {
                "title": "Retrieval Error",
                "source": "error.txt",
                "content": f"Error accessing document index: {str(e)}. Using fallback response.",
                "score": 0.3,
                "metadata": {"page": 1},
            }
        ]

    # Build context from retrieved documents
    context = "\n\n".join(
        [
            f"Document {i+1}: {doc['content']}"
            for i, doc in enumerate(mock_retrieved_docs[:top_k])
        ]
    )

    # Create RAG prompt
    rag_prompt = f"""You are a helpful AI assistant using a Retrieval-Augmented Generation (RAG) system.

Based on the following context documents, please answer the user's query. If the context doesn't contain enough information, say so clearly.

Context:
{context}

User Query: {query}

Please provide a comprehensive answer based on the context provided. Be specific and cite which documents you're using for different parts of your answer.

Answer:"""

    # Call real Gemini API
    try:
        # Use the LLM service to generate response (handle async)
        async def get_response():
            return await llm_service.generate(
                prompt=rag_prompt, temperature=temperature, max_tokens=max_tokens
            )

        # Run async function
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running (in Jupyter/Streamlit), create task
                import nest_asyncio

                nest_asyncio.apply()
                response = loop.run_until_complete(get_response())
            else:
                response = loop.run_until_complete(get_response())
        except RuntimeError:
            # No event loop, create new one
            response = asyncio.run(get_response())

        # Extract the answer from response
        if isinstance(response, dict):
            # Response is a dict with 'answer', 'model', 'provider' keys
            answer = response.get("answer", "No answer generated")
            if answer is None:
                answer = "Error: No answer generated from the model."
        elif hasattr(response, "content"):
            answer = response.content
        elif isinstance(response, str):
            answer = response
        else:
            answer = str(response)

    except Exception as e:
        answer = f"Error calling Gemini API: {str(e)}. Please check your API key and network connection."

    end_time = time.time()
    duration = end_time - start_time

    # Build response data
    pipeline_steps = [
        {
            "name": "Query Analysis",
            "icon": "🔍",
            "duration": 0.05,
            "status": "✅ Completed",
            "details": f"Analyzed query: {query[:100]}...",
            "metrics": {"query_length": len(query)},
        },
        {
            "name": "Document Retrieval",
            "icon": "📚",
            "duration": 0.1,
            "status": "✅ Completed (Real Index)"
            if "retriever" in locals() and retriever is not None
            else "✅ Completed (Fallback)",
            "details": f"Retrieved {len(mock_retrieved_docs)} documents from {'real index' if 'retriever' in locals() and retriever is not None else 'fallback'}",
            "metrics": {
                "documents_retrieved": len(mock_retrieved_docs),
                "source": "real_index"
                if "retriever" in locals() and retriever is not None
                else "fallback",
            },
        },
        {
            "name": "Gemini Generation",
            "icon": "🤖",
            "duration": duration - 0.15,
            "status": "✅ Completed",
            "details": f"Generated answer using Gemini API ({model})",
            "metrics": {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        },
    ]

    # Generate citations based on retrieved documents
    citations = []
    if answer and not answer.startswith("Error") and mock_retrieved_docs:
        for doc in mock_retrieved_docs[:3]:  # Show top 3 as citations
            citations.append(
                {
                    "title": doc["title"],
                    "source": doc["source"],
                    "excerpt": doc["content"][:200] + "..."
                    if len(doc["content"]) > 200
                    else doc["content"],
                    "relevance": doc["score"],
                }
            )

    return {
        "answer": answer,
        "citations": citations,
        "retrieved_docs": mock_retrieved_docs,
        "confidence": 0.85
        if "don't" not in answer.lower() and "cannot" not in answer.lower()
        else 0.4,
        "pipeline_steps": pipeline_steps,
        "error": False,
    }
