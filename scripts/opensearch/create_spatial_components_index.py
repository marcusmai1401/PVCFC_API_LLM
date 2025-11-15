#!/usr/bin/env python
"""
Create OpenSearch Spatial Components Index
Create index for spatial component-based proximity search (Level 2)

Usage:
    python scripts/opensearch/create_spatial_components_index.py [--delete-if-exists]
"""

import argparse
import sys
from pathlib import Path

from loguru import logger
from opensearchpy import OpenSearch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.spatial.schemas import SPATIAL_INDEX_MAPPING, SPATIAL_INDEX_NAME


def create_opensearch_client() -> OpenSearch:
    """Create OpenSearch client from environment"""
    import os

    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        timeout=30,
        max_retries=3,
        retry_on_timeout=True,
        use_ssl=False,
        verify_certs=False,
    )

    # Test connection
    try:
        info = client.info()
        logger.info(f"Connected to OpenSearch: {info['version']['number']}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch: {e}")
        sys.exit(1)


def create_spatial_components_index(
    client: OpenSearch,
    index_name: str,
    delete_if_exists: bool = False,
) -> bool:
    """
    Create spatial components index with proper mapping

    Args:
        client: OpenSearch client
        index_name: Index name (default: pvcfc_pid_spatial_components)
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

        # Create index with mapping
        logger.info(f"Creating index: {index_name}")
        response = client.indices.create(
            index=index_name,
            body=SPATIAL_INDEX_MAPPING,
        )

        if response.get("acknowledged"):
            logger.info(f"[OK] Index created successfully: {index_name}")

            # Verify mapping
            mapping = client.indices.get_mapping(index=index_name)
            props = mapping[index_name]["mappings"]["properties"]
            logger.info(f"  Properties: {len(props)} fields")
            logger.info(
                f"  Key fields: doc_id, page, component, component_type, bbox, center_x, center_y"
            )

            # Show index settings
            settings = client.indices.get_settings(index=index_name)
            shards = settings[index_name]["settings"]["index"]["number_of_shards"]
            replicas = settings[index_name]["settings"]["index"]["number_of_replicas"]
            logger.info(f"  Shards: {shards}, Replicas: {replicas}")

            return True
        else:
            logger.error("Index creation not acknowledged")
            return False

    except Exception as e:
        logger.error(f"Failed to create index: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Create OpenSearch spatial components index for Level 2 proximity search"
    )
    parser.add_argument(
        "--delete-if-exists",
        action="store_true",
        help="Delete existing index if present",
    )
    parser.add_argument(
        "--index-name",
        default=SPATIAL_INDEX_NAME,
        help=f"Index name (default: {SPATIAL_INDEX_NAME})",
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("CREATE OPENSEARCH SPATIAL COMPONENTS INDEX")
    logger.info("=" * 80)
    logger.info(f"Index name: {args.index_name}")
    logger.info(f"Delete if exists: {args.delete_if_exists}")
    logger.info("=" * 80)

    # Create client
    client = create_opensearch_client()

    # Create index
    success = create_spatial_components_index(
        client,
        args.index_name,
        args.delete_if_exists,
    )

    if success:
        logger.info("=" * 80)
        logger.info("[OK] Spatial components index ready!")
        logger.info("=" * 80)
        logger.info("\nNext steps:")
        logger.info("1. Run ingestion with --enable-pid-tags")
        logger.info("2. Components will be indexed automatically")
        logger.info("3. Level 2 spatial search will be available")
        logger.info("")
        sys.exit(0)
    else:
        logger.error("Failed to create spatial components index")
        sys.exit(1)


if __name__ == "__main__":
    main()
