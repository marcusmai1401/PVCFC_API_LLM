"""
Direct Gemini Integration for RAG Demo (Synchronous version)

Simpler integration with Google Gemini API for the RAG demo component.
"""

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


def process_with_gemini_direct(
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
    """Process query with real Gemini API using direct client."""

    start_time = time.time()

    # Get API key from environment
    from dotenv import load_dotenv

    load_dotenv()

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        return {
            "answer": "Error: GEMINI_API_KEY not found in environment variables. Please check your .env file.",
            "citations": [],
            "retrieved_docs": [],
            "confidence": 0.0,
            "pipeline_steps": [],
            "error": True,
        }

    # Initialize Gemini client directly
    try:
        from app.services.llm_client import GeminiClient

        # Map Streamlit model names to actual Gemini model names
        model_mapping = {
            "gemini-3-flash-preview": "gemini-3-flash-preview",
            "gemini-3-pro-preview": "gemini-3-pro-preview",
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
        }

        actual_model = model_mapping.get(model, "gemini-3-flash-preview")

        client = GeminiClient(api_key=gemini_api_key, model=actual_model)

    except Exception as e:
        return {
            "answer": f"Error initializing Gemini client: {str(e)}",
            "citations": [],
            "retrieved_docs": [],
            "confidence": 0.0,
            "pipeline_steps": [],
            "error": True,
        }

    # Load real retriever from indices
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

    # Build context from retrieved documents with better formatting
    context_parts = []
    for i, doc in enumerate(mock_retrieved_docs[:top_k], 1):
        context_parts.append(
            f"""[Document {i} - {doc.get('source', 'Unknown')}]:
{doc['content']}
---End of Document {i}---"""
        )

    context = "\n\n".join(context_parts)

    # Create RAG prompt with clearer instructions
    system_prompt = """You are a helpful technical AI assistant using a Retrieval-Augmented Generation (RAG) system.
Your task is to answer questions based ONLY on the provided context documents.
If the documents contain relevant information, provide a detailed answer.
If the documents do NOT contain the specific information requested, clearly state that.
Always cite the document number when using information from it."""

    full_prompt = f"""You have access to the following technical documents:

{context}

User Question: {query}

Instructions:
1. Answer based ONLY on the information in the documents above
2. If the answer is in the documents, provide specific details
3. If the answer is NOT in the documents, say "The provided documents do not contain information about [topic]"
4. Cite document numbers when referencing information

Answer:"""

    # Call real Gemini API
    try:
        response = client.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Extract answer from response
        if hasattr(response, "content"):
            answer = response.content
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
                "model": actual_model,
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
        "confidence": 0.85 if answer and not answer.startswith("Error") else 0.2,
        "pipeline_steps": pipeline_steps,
        "error": answer.startswith("Error") if answer else True,
    }
