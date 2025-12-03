"""
Test OpenSearch BM25 search functionality

This script tests the rag_chunks index with various queries to verify:
- BM25 search works correctly
- Field boosts are applied
- Filters work (doc_type, page ranges, etc.)
- Results are relevant

Usage:
    python scripts/opensearch/test_opensearch_search.py [query]

Examples:
    python scripts/opensearch/test_opensearch_search.py "CO2 compressor"
    python scripts/opensearch/test_opensearch_search.py "torque"
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from opensearchpy import OpenSearch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configuration
INDEX_NAME = "rag_chunks"
OS_HOST = "localhost"
OS_PORT = 9200


def create_opensearch_client():
    """Create OpenSearch client connection"""
    try:
        client = OpenSearch(
            hosts=[{"host": OS_HOST, "port": OS_PORT}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            timeout=30,
        )
        return client
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch: {e}")
        sys.exit(1)


def bm25_search(
    client: OpenSearch,
    query: str,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Search using BM25 with multi_match query

    Args:
        client: OpenSearch client
        query: Search query string
        top_k: Number of results to return
        filters: Optional filters (doc_type, doc_ids, page_min, page_max)

    Returns:
        List of search results
    """
    # Build must clauses (search query)
    must = [
        {
            "multi_match": {
                "query": query,
                "fields": [
                    "text^3",  # Main text with highest boost
                    "heading^2",  # Headings with medium boost
                    "title",  # Title with default boost
                ],
                "type": "best_fields",
                "operator": "or",  # Use 'and' for higher precision
            }
        }
    ]

    # Build filter clauses
    filter_clauses = []
    if filters:
        if filters.get("doc_type"):
            doc_types = filters["doc_type"]
            if not isinstance(doc_types, list):
                doc_types = [doc_types]
            filter_clauses.append({"terms": {"doc_type": doc_types}})

        if filters.get("doc_ids"):
            doc_ids = filters["doc_ids"]
            if not isinstance(doc_ids, list):
                doc_ids = [doc_ids]
            filter_clauses.append({"terms": {"doc_id": doc_ids}})

        if filters.get("page_min") or filters.get("page_max"):
            rng = {}
            if filters.get("page_min") is not None:
                rng["gte"] = filters["page_min"]
            if filters.get("page_max") is not None:
                rng["lte"] = filters["page_max"]
            filter_clauses.append({"range": {"page": rng}})

    # Build query body
    body = {
        "size": top_k,
        "query": {"bool": {"must": must, "filter": filter_clauses}},
        "highlight": {
            "fields": {"text": {"fragment_size": 150, "number_of_fragments": 2}}
        },
        "_source": [
            "chunk_id",
            "doc_id",
            "text",
            "page",
            "page_start",
            "page_end",
            "heading",
            "title",
            "doc_type",
        ],
    }

    # Execute search
    response = client.search(index=INDEX_NAME, body=body)
    hits = response["hits"]["hits"]

    # Parse results
    results = []
    for h in hits:
        src = h.get("_source", {})
        highlight = h.get("highlight", {}).get("text", [])

        results.append(
            {
                "chunk_id": src.get("chunk_id"),
                "doc_id": src.get("doc_id"),
                "text": src.get("text", "")[:200] + "...",  # Truncate for display
                "score": h.get("_score", 0.0),
                "page": src.get("page"),
                "page_start": src.get("page_start"),
                "page_end": src.get("page_end"),
                "heading": src.get("heading"),
                "title": src.get("title"),
                "doc_type": src.get("doc_type"),
                "highlight": highlight,
            }
        )

    return results


def run_test_queries(client: OpenSearch):
    """Run a suite of test queries"""
    test_queries = [
        {"query": "CO2 compressor", "top_k": 5, "description": "CO2 compressor search"},
        {
            "query": "torque",
            "top_k": 5,
            "description": "Torque-related documents",
        },
        {
            "query": "performance curve",
            "top_k": 5,
            "description": "Performance curves",
        },
        {
            "query": "maintenance procedure",
            "top_k": 5,
            "description": "Maintenance procedures",
        },
    ]

    logger.info("=" * 80)
    logger.info("Running Test Queries")
    logger.info("=" * 80)

    for test in test_queries:
        logger.info(f"\n🔍 Query: '{test['query']}' - {test['description']}")
        logger.info("-" * 80)

        results = bm25_search(client, test["query"], top_k=test["top_k"])

        if not results:
            logger.warning("  No results found")
            continue

        for i, result in enumerate(results, 1):
            logger.info(f"\n  {i}. Score: {result['score']:.4f}")
            logger.info(f"     Doc: {result['doc_id']}")
            logger.info(f"     Page: {result['page']}")
            if result.get("heading"):
                logger.info(f"     Heading: {result['heading']}")
            if result.get("highlight"):
                logger.info(f"     Highlight: {result['highlight'][0][:100]}...")
            logger.info(f"     Text: {result['text'][:100]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Test OpenSearch BM25 search on rag_chunks index"
    )
    parser.add_argument("query", nargs="?", help="Search query (optional)")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results")
    parser.add_argument(
        "--test-suite", action="store_true", help="Run predefined test suite"
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("OpenSearch BM25 Search Test")
    logger.info("=" * 80)

    # Create client
    client = create_opensearch_client()

    # Verify index
    if not client.indices.exists(index=INDEX_NAME):
        logger.error(f"Index '{INDEX_NAME}' does not exist")
        sys.exit(1)

    # Get index stats
    count = client.count(index=INDEX_NAME)["count"]
    logger.info(f"Index '{INDEX_NAME}' has {count} documents\n")

    if args.test_suite:
        # Run test suite
        run_test_queries(client)
    elif args.query:
        # Run single query
        logger.info(f"Searching for: '{args.query}'\n")
        results = bm25_search(client, args.query, top_k=args.top_k)

        if not results:
            logger.warning("No results found")
            return

        for i, result in enumerate(results, 1):
            logger.info(f"\n{i}. Score: {result['score']:.4f}")
            logger.info(f"   Doc: {result['doc_id']}")
            logger.info(f"   Page: {result['page']}")
            if result.get("heading"):
                logger.info(f"   Heading: {result['heading']}")
            if result.get("doc_type"):
                logger.info(f"   Type: {result['doc_type']}")
            logger.info(f"   Text: {result['text']}")
            if result.get("highlight"):
                logger.info(f"   Highlight: {result['highlight'][0][:150]}...")
    else:
        logger.error("Please provide a query or use --test-suite")
        parser.print_help()
        sys.exit(1)

    logger.success("\n✓ Search test completed")


if __name__ == "__main__":
    main()
