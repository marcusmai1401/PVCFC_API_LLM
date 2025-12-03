#!/usr/bin/env python
"""Check chunks with page=0 in OpenSearch to determine if they are valid"""

import os

from loguru import logger
from opensearchpy import OpenSearch

# Chunks that returned page=0
suspicious_chunks = [
    "88c1bf31-105b-48fe-b488-26a58d7fe02e",
    "cdac9c07-1c59-4d5b-a993-9aadbbf078d2",
    "4e411009-c7a1-4716-89fd-0ced21b2c0b5",
]


def check_chunks_in_opensearch():
    """Check what page values are stored for these chunks"""

    # Load credentials from environment variables (optional for no-security mode)
    OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
    OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD")

    # Connect with or without authentication based on security mode
    if OPENSEARCH_PASSWORD:
        client = OpenSearch(
            hosts=[{"host": "localhost", "port": 9200}],
            http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )
    else:
        client = OpenSearch(
            hosts=[{"host": "localhost", "port": 9200}],
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )

    logger.info("Checking chunks with page=0 in OpenSearch...")
    logger.info("=" * 80)

    for chunk_id in suspicious_chunks:
        logger.info(f"\nChunk ID: {chunk_id}")

        # Search for this chunk
        query = {"query": {"term": {"chunk_id.keyword": chunk_id}}}

        try:
            response = client.search(index="rag_chunks", body=query)

            if response["hits"]["total"]["value"] == 0:
                logger.warning(f"  ⚠️  Chunk not found in OpenSearch")
                continue

            hit = response["hits"]["hits"][0]
            source = hit["_source"]

            logger.info(f"  Page in OpenSearch: {source.get('page')}")
            logger.info(f"  Doc ID: {source.get('doc_id')}")
            logger.info(f"  Text preview: {source.get('text', '')[:100]}...")

            # Check if page=0 is legitimate
            page = source.get("page")
            if page == 0:
                logger.warning(
                    f"  ⚠️  Page=0 is STORED in OpenSearch (possibly cover page or metadata)"
                )
            elif page is None:
                logger.error(f"  ❌ Page is None in OpenSearch (data quality issue)")
            else:
                logger.info(f"  ✅ Page={page} in OpenSearch")

        except Exception as e:
            logger.error(f"  ❌ Error querying OpenSearch: {e}")

    logger.info("\n" + "=" * 80)
    logger.info("Conclusion:")
    logger.info("If page=0 is stored in OpenSearch, this is likely:")
    logger.info("  1. Cover page or title page (legitimate page=0)")
    logger.info("  2. Data indexing issue where page wasn't extracted properly")
    logger.info("  3. Document metadata that doesn't have page numbers")


if __name__ == "__main__":
    check_chunks_in_opensearch()
