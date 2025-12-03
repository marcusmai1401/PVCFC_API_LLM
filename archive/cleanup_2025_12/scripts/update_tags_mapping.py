"""
Update OpenSearch Mapping to Add Tags Field

One-time migration script to add tags and tags_raw fields to rag_chunks index
This uses dynamic mapping so no reindex is required
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger
from opensearchpy import OpenSearch

from app.core.config import settings


def add_tags_field():
    """Add tags field to OpenSearch mapping"""

    logger.info("=" * 80)
    logger.info("UPDATING OPENSEARCH MAPPING: Adding tags field")
    logger.info("=" * 80)

    # Connect to OpenSearch
    client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=30,
    )

    logger.info(
        f"Connected to OpenSearch: {settings.opensearch_host}:{settings.opensearch_port}"
    )

    # Check if index exists
    index_name = settings.opensearch_index
    if not client.indices.exists(index=index_name):
        logger.error(f"Index '{index_name}' does not exist!")
        return False

    logger.info(f"Index '{index_name}' exists")

    # Update mapping to add tags fields
    mapping_update = {
        "properties": {
            "tags": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "tags_raw": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
        }
    }

    logger.info("Adding tags and tags_raw fields to mapping...")

    try:
        response = client.indices.put_mapping(index=index_name, body=mapping_update)

        logger.info(f"Mapping update response: {response}")

        if response.get("acknowledged"):
            logger.info("✅ Successfully added tags fields to OpenSearch mapping")
            logger.info("")
            logger.info("Fields added:")
            logger.info("  - tags (text + keyword)")
            logger.info("  - tags_raw (text + keyword)")
            logger.info("")
            logger.info("Note: No reindex required (dynamic mapping)")
            return True
        else:
            logger.error("❌ Mapping update was not acknowledged")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to update mapping: {e}")
        logger.exception(e)
        return False


if __name__ == "__main__":
    success = add_tags_field()
    sys.exit(0 if success else 1)
