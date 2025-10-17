#!/usr/bin/env python
"""
Create OpenSearch Tags Index
Create sidecar index for PID tags with n-gram analyzer

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 7
Usage:
    python scripts/opensearch/create_tags_index.py [--delete-if-exists]
"""

import argparse
import json
import sys
from pathlib import Path

from loguru import logger
from opensearchpy import OpenSearch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_config


def create_opensearch_client() -> OpenSearch:
    """Create OpenSearch client from config"""
    config = get_config()

    # Get OpenSearch settings from environment
    import os

    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        timeout=30,
        max_retries=3,
        retry_on_timeout=True,
    )

    # Test connection
    try:
        info = client.info()
        logger.info(f"Connected to OpenSearch: {info['version']['number']}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch: {e}")
        sys.exit(1)


def create_tags_index(
    client: OpenSearch,
    index_name: str,
    mapping_file: Path,
    delete_if_exists: bool = False,
) -> bool:
    """
    Create tags index with mapping from config file

    Args:
        client: OpenSearch client
        index_name: Index name (e.g., "pvcfc_pid_tags")
        mapping_file: Path to tags_index_mapping.json
        delete_if_exists: Delete existing index if present

    Returns:
        True if successful
    """
    try:
        # Check if index exists
        exists = client.indices.exists(index=index_name)

        if exists:
            if delete_if_exists:
                logger.warning(f"Deleting existing index: {index_name}")
                client.indices.delete(index=index_name)
            else:
                logger.info(f"Index already exists: {index_name}")
                return True

        # Load mapping
        with open(mapping_file, "r", encoding="utf-8") as f:
            index_config = json.load(f)

        # Create index
        logger.info(f"Creating index: {index_name}")
        response = client.indices.create(
            index=index_name,
            body=index_config,
        )

        if response.get("acknowledged"):
            logger.info(f"✓ Index created successfully: {index_name}")

            # Verify mapping
            mapping = client.indices.get_mapping(index=index_name)
            props = mapping[index_name]["mappings"]["properties"]
            logger.info(f"  Properties: {len(props)} fields")
            logger.info(f"  Key fields: tag, area, code, num, suffix, bbox")

            return True
        else:
            logger.error("Index creation not acknowledged")
            return False

    except Exception as e:
        logger.error(f"Failed to create index: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Create OpenSearch tags sidecar index")
    parser.add_argument(
        "--delete-if-exists",
        action="store_true",
        help="Delete existing index if present",
    )
    parser.add_argument(
        "--index-name",
        default=None,
        help="Index name (default from config: pvcfc_pid_tags)",
    )

    args = parser.parse_args()

    # Get config
    config = get_config()

    index_name = args.index_name or config.TAGS_INDEX_NAME
    mapping_file = config.TAGS_INDEX_MAPPING_CONFIG

    if not mapping_file.exists():
        logger.error(f"Mapping file not found: {mapping_file}")
        logger.error("Expected: config/tags_index_mapping.json")
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("CREATE OPENSEARCH TAGS INDEX")
    logger.info("=" * 80)
    logger.info(f"Index name: {index_name}")
    logger.info(f"Mapping file: {mapping_file}")
    logger.info(f"Delete if exists: {args.delete_if_exists}")
    logger.info("=" * 80)

    # Create client
    client = create_opensearch_client()

    # Create index
    success = create_tags_index(
        client,
        index_name,
        mapping_file,
        args.delete_if_exists,
    )

    if success:
        logger.info("=" * 80)
        logger.info("✓ Tags index ready!")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("Failed to create tags index")
        sys.exit(1)


if __name__ == "__main__":
    main()
