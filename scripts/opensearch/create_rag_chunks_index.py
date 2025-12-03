"""
Create OpenSearch index for RAG chunks with BM25 similarity

This script creates the 'rag_chunks' index with:
- BM25 similarity (k1=1.2, b=0.75) matching offline rank-bm25 config
- Standard analyzer for EN/VI text
- Proper field mappings for all metadata
- Optimized for keyword + semantic hybrid search

Usage:
    python scripts/opensearch/create_rag_chunks_index.py [--delete-if-exists]

Requirements:
    pip install opensearch-py
"""

import argparse
import sys
from pathlib import Path

from loguru import logger
from opensearchpy import OpenSearch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Index configuration
INDEX_NAME = "rag_chunks"
OS_HOST = "localhost"
OS_PORT = 9200

# Index settings and mappings
INDEX_BODY = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "1s",
            "max_result_window": 10000,  # Allow deep pagination if needed
            "similarity": {
                "default": {
                    "type": "BM25",
                    "b": 0.75,  # Length normalization (same as rank-bm25)
                    "k1": 1.2,  # Term frequency saturation (same as rank-bm25)
                }
            },
        },
        "analysis": {
            "analyzer": {
                "default": {
                    "type": "standard",  # Good for both EN and VI
                }
            }
        },
    },
    "mappings": {
        "properties": {
            # Core identifiers
            "chunk_id": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            # Main searchable text fields
            "text": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256,
                    }
                },
            },
            "heading": {
                "type": "text",
                "analyzer": "standard",
                "fields": {"raw": {"type": "keyword", "ignore_above": 256}},
            },
            "title": {
                "type": "text",
                "analyzer": "standard",
                "fields": {"raw": {"type": "keyword", "ignore_above": 256}},
            },
            # Document metadata
            "author": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "revision": {"type": "keyword"},
            "source_format": {"type": "keyword"},  # vector|scan
            "file_name": {"type": "keyword"},
            # Chunk structure
            "chunk_index": {"type": "integer"},
            "parent_chunk_id": {"type": "keyword"},
            "level": {"type": "integer"},
            # Page information (critical for citations)
            "page": {"type": "integer"},
            "page_start": {"type": "integer"},
            "page_end": {"type": "integer"},
            "page_nums": {"type": "integer"},  # For compatibility
            # Table metadata
            "has_table": {"type": "boolean"},
            "table_count": {"type": "integer"},
            "table_keywords": {"type": "keyword"},
            "has_torque_data": {"type": "boolean"},
            # Additional metadata (for future expansion)
            "equipment_id": {"type": "keyword"},
            "language": {"type": "keyword"},
            "year": {"type": "integer"},
            # Classification metadata (v2.0 - Intelligent Auto-Classification)
            "category": {
                "type": "keyword",
                "doc_values": True,
            },
            "classification_status": {
                "type": "keyword",  # classified | needs_review | pending
                "doc_values": True,
            },
            "classification_confidence": {
                "type": "float",
            },
            "classification_method": {
                "type": "keyword",  # cadlike_gate | ai_classifier | manual
                "doc_values": True,
            },
        }
    },
}


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
        # Test connection
        info = client.info()
        logger.info(f"Connected to OpenSearch: {info['version']['number']}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch at {OS_HOST}:{OS_PORT}")
        logger.error(f"Error: {e}")
        logger.error("Make sure OpenSearch is running: docker-compose up -d opensearch")
        sys.exit(1)


def create_index(client: OpenSearch, delete_if_exists: bool = False):
    """Create the rag_chunks index"""
    try:
        # Check if index exists
        exists = client.indices.exists(index=INDEX_NAME)

        if exists:
            if delete_if_exists:
                logger.warning(f"Index '{INDEX_NAME}' exists. Deleting...")
                client.indices.delete(index=INDEX_NAME)
                logger.info(f"Deleted existing index '{INDEX_NAME}'")
            else:
                logger.error(
                    f"Index '{INDEX_NAME}' already exists. Use --delete-if-exists to recreate."
                )
                return False

        # Create index
        logger.info(f"Creating index '{INDEX_NAME}'...")
        response = client.indices.create(index=INDEX_NAME, body=INDEX_BODY)

        logger.success(f"✓ Index '{INDEX_NAME}' created successfully")
        logger.info(f"Response: {response}")

        # Verify settings
        settings = client.indices.get_settings(index=INDEX_NAME)
        similarity = settings[INDEX_NAME]["settings"]["index"]["similarity"]["default"]
        logger.info(f"BM25 settings: k1={similarity['k1']}, b={similarity['b']}")

        # Get mapping info
        mappings = client.indices.get_mapping(index=INDEX_NAME)
        props = mappings[INDEX_NAME]["mappings"]["properties"]
        logger.info(f"Mapped {len(props)} fields")

        return True

    except Exception as e:
        logger.error(f"Failed to create index: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Create OpenSearch rag_chunks index with BM25 similarity"
    )
    parser.add_argument(
        "--delete-if-exists",
        action="store_true",
        help="Delete existing index before creating",
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("OpenSearch Index Creation - rag_chunks")
    logger.info("=" * 80)

    # Create client
    client = create_opensearch_client()

    # Create index
    success = create_index(client, delete_if_exists=args.delete_if_exists)

    if success:
        logger.success("\n✓ Index creation completed successfully")
        logger.info(f"\nNext step: Run bulk_insert_to_opensearch.py to load data")
    else:
        logger.error("\n✗ Index creation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
