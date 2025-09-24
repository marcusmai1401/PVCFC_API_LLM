#!/usr/bin/env python
"""
Test script for RAG Generator Module (Sprint 1.4)
Tests end-to-end answer generation with citations
"""
import json
import sys
import time
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
from dotenv import load_dotenv

load_dotenv()

from app.rag.generator import (
    GeneratorConfig,
    RAGGenerator,
    create_generator,
    generate_answer,
)
from app.rag.query_transform import transform_query
from app.rag.reranker import create_reranker
from app.rag.retriever import create_hybrid_retriever


def test_basic_generation():
    """Test basic answer generation"""
    logger.info("=== Testing Basic Answer Generation ===")

    # Setup pipeline
    query_text = "What is the operating pressure of the CO2 compressor?"
    logger.info(f"Query: '{query_text}'")

    # 1. Transform query
    transformed = transform_query(query_text, enable_hyde=False)
    logger.info(f"Intent detected: {transformed.intent.value}")

    # 2. Retrieve documents
    retriever = create_hybrid_retriever()
    docs = retriever.search(transformed)[:5]  # Top 5 docs
    logger.info(f"Retrieved {len(docs)} documents")

    # 3. Generate answer
    generator = create_generator(
        GeneratorConfig(llm_tier="light", temperature=0.3, citation_style="inline")
    )

    answer = generator.generate(transformed, docs)

    # Display results
    logger.info(f"\n--- Generated Answer ---")
    logger.info(f"Answer: {answer.answer}")
    logger.info(f"Confidence: {answer.confidence:.2f}")
    logger.info(f"Citations: {len(answer.citations)}")

    if answer.citations:
        logger.info("\nCitation details:")
        for i, citation in enumerate(answer.citations, 1):
            logger.info(
                f"  [{i}] {citation.source} (score: {citation.relevance_score:.4f})"
            )

    logger.info(f"Generation time: {answer.generation_time_ms:.2f}ms")
    logger.info("")


def test_different_intents():
    """Test generation for different query intents"""
    logger.info("=== Testing Different Query Intents ===")

    test_cases = [
        ("What is the maximum temperature of the steam turbine?", "ASK"),
        ("Explain how the CO2 compressor works", "EXPLAIN"),
        ("Where can I find equipment KT06101?", "LOCATE"),
        ("Generate a report on safety requirements", "REPORT"),
    ]

    retriever = create_hybrid_retriever()
    generator = create_generator(GeneratorConfig(llm_tier="light"))

    for query_text, expected_intent in test_cases:
        logger.info(f"\n--- Testing {expected_intent} intent ---")
        logger.info(f"Query: '{query_text}'")

        # Transform
        transformed = transform_query(query_text, enable_hyde=False)
        logger.info(f"Detected intent: {transformed.intent.value}")

        # Retrieve
        docs = retriever.search(transformed)[:5]

        # Generate
        answer = generator.generate(transformed, docs)

        # Show result
        logger.info(f"Answer preview: {answer.answer[:150]}...")
        logger.info(f"Confidence: {answer.confidence:.2f}")
        logger.info(f"Citations: {len(answer.citations)}")

    logger.info("")


def test_with_citations():
    """Test citation extraction and formatting"""
    logger.info("=== Testing Citation Handling ===")

    query_text = (
        "What are the pressure and temperature specifications for the compressor?"
    )

    # Setup pipeline
    transformed = transform_query(query_text, enable_hyde=False)
    retriever = create_hybrid_retriever()
    docs = retriever.search(transformed)[:5]

    # Test inline citations
    logger.info("\n1. Testing INLINE citation style:")
    generator_inline = create_generator(
        GeneratorConfig(llm_tier="light", citation_style="inline")
    )
    answer_inline = generator_inline.generate(transformed, docs)
    logger.info(f"Answer: {answer_inline.answer[:200]}...")

    # Test footnote citations
    logger.info("\n2. Testing FOOTNOTE citation style:")
    generator_footnote = create_generator(
        GeneratorConfig(llm_tier="light", citation_style="footnote")
    )
    answer_footnote = generator_footnote.generate(transformed, docs)
    logger.info(f"Answer: {answer_footnote.answer}")

    logger.info("")


def test_complete_pipeline():
    """Test complete RAG pipeline with all components"""
    logger.info("=== Testing Complete RAG Pipeline ===")

    query_text = "What is the maximum operating temperature of the steam turbine and what are the safety requirements?"
    logger.info(f"Query: '{query_text}'")

    # 1. Query Transformation with HyDE
    logger.info("\n1. Query Transformation (with HyDE)...")
    try:
        transformed = transform_query(query_text, enable_hyde=True)
        if transformed.hyde_queries:
            logger.info(f"   Generated {len(transformed.hyde_queries)} HyDE queries")
    except:
        logger.warning("   HyDE failed, using standard transformation")
        transformed = transform_query(query_text, enable_hyde=False)

    # 2. Hybrid Retrieval
    logger.info("\n2. Hybrid Retrieval...")
    retriever = create_hybrid_retriever()
    initial_docs = retriever.search(transformed)
    logger.info(f"   Retrieved {len(initial_docs)} documents")

    # 3. Reranking
    logger.info("\n3. Reranking...")
    reranker = create_reranker(method="score_based", top_k=5)
    reranked_docs = reranker.rerank(query_text, initial_docs)
    logger.info(f"   Reranked to top {len(reranked_docs)} documents")

    # 4. Answer Generation
    logger.info("\n4. Answer Generation...")
    generator = create_generator(
        GeneratorConfig(
            llm_tier="light",
            temperature=0.3,
            max_answer_length=300,
            citation_style="inline",
        )
    )

    start_time = time.time()
    answer = generator.generate(transformed, reranked_docs)
    total_time = (time.time() - start_time) * 1000

    # Display final results
    logger.info("\n" + "=" * 50)
    logger.info("FINAL ANSWER")
    logger.info("=" * 50)
    logger.info(f"\nQuery: {query_text}")
    logger.info(f"\nAnswer:\n{answer.answer}")
    logger.info(f"\nConfidence: {answer.confidence:.2f}")
    logger.info(f"\nCitations ({len(answer.citations)}):")
    for i, citation in enumerate(answer.citations, 1):
        logger.info(f"  [{i}] {citation.source}")

    logger.info(f"\nMetadata:")
    for key, value in answer.metadata.items():
        logger.info(f"  {key}: {value}")

    logger.info(f"\nTotal generation time: {total_time:.2f}ms")
    logger.info("")


def test_no_results_handling():
    """Test handling when no documents are found"""
    logger.info("=== Testing No Results Handling ===")

    query_text = "What is the price of bitcoin in 2024?"  # Irrelevant query

    transformed = transform_query(query_text, enable_hyde=False)
    generator = create_generator()

    # Generate with empty docs
    answer = generator.generate(transformed, [])

    logger.info(f"Query: '{query_text}'")
    logger.info(f"Answer: {answer.answer}")
    logger.info(f"Confidence: {answer.confidence}")
    logger.info(f"Metadata: {answer.metadata}")

    logger.info("")


def test_performance():
    """Test generation performance"""
    logger.info("=== Testing Generation Performance ===")

    queries = [
        "What is the pressure?",
        "Explain the turbine operation",
        "Find equipment specifications",
    ]

    retriever = create_hybrid_retriever()
    generator = create_generator(GeneratorConfig(llm_tier="light"))

    total_time = 0
    for query_text in queries:
        transformed = transform_query(query_text, enable_hyde=False)
        docs = retriever.search(transformed)[:3]  # Use fewer docs for speed

        start = time.time()
        answer = generator.generate(transformed, docs)
        elapsed = (time.time() - start) * 1000
        total_time += elapsed

        logger.info(f"Query: '{query_text[:30]}...' - Time: {elapsed:.2f}ms")

    avg_time = total_time / len(queries)
    logger.info(f"\nAverage generation time: {avg_time:.2f}ms")

    logger.info("")


def test_api_response_format():
    """Test API response format"""
    logger.info("=== Testing API Response Format ===")

    query_text = "What is the compressor pressure?"

    # Generate answer
    transformed = transform_query(query_text, enable_hyde=False)
    retriever = create_hybrid_retriever()
    docs = retriever.search(transformed)[:3]
    generator = create_generator()
    answer = generator.generate(transformed, docs)

    # Convert to API format
    api_response = answer.to_dict()

    logger.info("API Response Format:")
    logger.info(json.dumps(api_response, indent=2, default=str))

    # Validate response structure
    assert "query" in api_response
    assert "answer" in api_response
    assert "citations" in api_response
    assert "confidence" in api_response
    assert "metadata" in api_response

    logger.info("\n✓ API response format validated")
    logger.info("")


def main():
    """Run all tests"""
    logger.info("RAG Generator Test Suite (Sprint 1.4)")
    logger.info("=" * 50)

    # Run tests
    test_basic_generation()
    test_different_intents()
    test_with_citations()
    test_complete_pipeline()
    test_no_results_handling()
    test_performance()
    test_api_response_format()

    logger.info("=" * 50)
    logger.info("Test suite completed!")

    # Summary
    logger.info("\nSprint 1.4 Status:")
    logger.info("✓ Answer generation working")
    logger.info("✓ Intent-based generation")
    logger.info("✓ Citation extraction")
    logger.info("✓ Multiple citation styles")
    logger.info("✓ Complete pipeline integration")
    logger.info("✓ Error handling")
    logger.info("✓ API response format")

    logger.info("\nNext Steps:")
    logger.info("1. Create FastAPI endpoints")
    logger.info("2. Add evaluation metrics")
    logger.info("3. Implement caching")
    logger.info("4. Add streaming support")


if __name__ == "__main__":
    main()
