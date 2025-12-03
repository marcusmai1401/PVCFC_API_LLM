#!/usr/bin/env python
"""
Cleanup Script for Weaviate and OpenSearch Indexes
Removes all data from vector DB and keyword search indexes
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from app.config import get_config

# Try to import Weaviate client
try:
    import weaviate
    from weaviate.classes.config import Configure

    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False
    logger.warning("Weaviate client not available")

# Try to import OpenSearch client
try:
    from opensearchpy import OpenSearch

    OPENSEARCH_AVAILABLE = True
except ImportError:
    OPENSEARCH_AVAILABLE = False
    logger.warning("OpenSearch client not available")


def cleanup_weaviate():
    """Delete Weaviate collection"""
    if not WEAVIATE_AVAILABLE:
        logger.warning("Weaviate client not available - skipping")
        return False

    config = get_config()

    try:
        logger.info("Connecting to Weaviate...")

        # Connect to Weaviate
        if config.WEAVIATE_USE_GRPC:
            client = weaviate.connect_to_local(
                host=config.WEAVIATE_HOST,
                port=config.WEAVIATE_PORT,
                grpc_port=config.WEAVIATE_GRPC_PORT,
            )
        else:
            client = weaviate.connect_to_local(
                host=config.WEAVIATE_HOST, port=config.WEAVIATE_PORT
            )

        logger.info(f"Checking for collection: {config.WEAVIATE_COLLECTION}")

        # Check if collection exists
        if client.collections.exists(config.WEAVIATE_COLLECTION):
            logger.warning(f"Deleting collection: {config.WEAVIATE_COLLECTION}")
            client.collections.delete(config.WEAVIATE_COLLECTION)
            logger.success(f"✓ Collection '{config.WEAVIATE_COLLECTION}' deleted")
        else:
            logger.info(
                f"Collection '{config.WEAVIATE_COLLECTION}' does not exist - nothing to delete"
            )

        client.close()
        return True

    except Exception as e:
        logger.error(f"Error cleaning Weaviate: {e}")
        return False


def cleanup_opensearch():
    """Delete OpenSearch indexes"""
    if not OPENSEARCH_AVAILABLE:
        logger.warning("OpenSearch client not available - skipping")
        return False

    config = get_config()

    try:
        logger.info("Connecting to OpenSearch...")

        # Connect to OpenSearch
        client = OpenSearch(
            hosts=[{"host": config.OPENSEARCH_HOST, "port": config.OPENSEARCH_PORT}],
            http_compress=True,
            timeout=config.OPENSEARCH_TIMEOUT,
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )

        # Check cluster health
        health = client.cluster.health()
        logger.info(
            f"OpenSearch cluster: {health['cluster_name']} - {health['status']}"
        )

        # Delete rag_chunks index
        index_name = config.OPENSEARCH_INDEX
        if client.indices.exists(index=index_name):
            logger.warning(f"Deleting index: {index_name}")
            client.indices.delete(index=index_name)
            logger.success(f"✓ Index '{index_name}' deleted")
        else:
            logger.info(f"Index '{index_name}' does not exist - nothing to delete")

        # Delete spatial components index (if exists)
        spatial_index = getattr(
            config, "SPATIAL_COMPONENTS_INDEX_NAME", "pvcfc_pid_spatial_components"
        )
        if client.indices.exists(index=spatial_index):
            logger.warning(f"Deleting index: {spatial_index}")
            client.indices.delete(index=spatial_index)
            logger.success(f"✓ Index '{spatial_index}' deleted")
        else:
            logger.info(f"Index '{spatial_index}' does not exist - nothing to delete")

        return True

    except Exception as e:
        logger.error(f"Error cleaning OpenSearch: {e}")
        return False


def main():
    """Main cleanup function"""
    logger.info("=" * 60)
    logger.info("CLEANUP: Weaviate & OpenSearch Indexes")
    logger.info("=" * 60)

    # Confirmation prompt
    print("\n⚠️  WARNING: This will DELETE all data from:")
    print("  - Weaviate collection (vector embeddings)")
    print("  - OpenSearch rag_chunks index (keyword search)")
    print("  - OpenSearch spatial_components index (P&ID tags)")
    print("\nThis action CANNOT be undone!\n")

    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()

    if response != "yes":
        logger.info("Cleanup cancelled by user")
        return

    logger.info("\nStarting cleanup...")

    # Cleanup Weaviate
    logger.info("\n[1/2] Cleaning Weaviate...")
    weaviate_success = cleanup_weaviate()

    # Cleanup OpenSearch
    logger.info("\n[2/2] Cleaning OpenSearch...")
    opensearch_success = cleanup_opensearch()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Weaviate: {'✓ SUCCESS' if weaviate_success else '✗ FAILED'}")
    logger.info(f"OpenSearch: {'✓ SUCCESS' if opensearch_success else '✗ FAILED'}")
    logger.info("=" * 60)

    if weaviate_success and opensearch_success:
        logger.success("\n✓ All indexes cleaned successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run ingestion: python tools/ingest.py ...")
        logger.info("2. Recreate indexes: python scripts/opensearch/create_*_index.py")
        logger.info(
            "3. Index chunks: python scripts/utilities/index_production_chunks.py"
        )
    else:
        logger.warning("\n⚠ Some cleanups failed - check logs above")


if __name__ == "__main__":
    main()
