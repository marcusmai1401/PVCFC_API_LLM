#!/usr/bin/env python
"""
Script to clear ALL data before full re-ingestion
Clears:
- OpenSearch indexes (rag_chunks, spatial_components)
- Weaviate collection (Chunk)
- Artifacts directories (ingestion_production, index_production)

WARNING: This will DELETE all existing data!
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables first
try:
    from dotenv import load_dotenv

    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded .env from {env_path}")
except ImportError:
    pass
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

import shutil

import weaviate
from loguru import logger
from opensearchpy import OpenSearch

# Import settings after setting up path and loading env
from app.core.config import settings


def clear_opensearch_indexes():
    """Delete and recreate OpenSearch indexes"""
    logger.info("=" * 80)
    logger.info("CLEARING OPENSEARCH INDEXES")
    logger.info("=" * 80)

    client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,
    )

    # Delete rag_chunks
    if client.indices.exists(index=settings.opensearch_index):
        logger.warning(f"Deleting index: {settings.opensearch_index}")
        client.indices.delete(index=settings.opensearch_index)
        logger.info(f"✓ Deleted {settings.opensearch_index}")

    # Delete spatial_components
    from app.rag.spatial.schemas import SPATIAL_INDEX_NAME

    spatial_index = SPATIAL_INDEX_NAME
    if client.indices.exists(index=spatial_index):
        logger.warning(f"Deleting index: {spatial_index}")
        client.indices.delete(index=spatial_index)
        logger.info(f"✓ Deleted {spatial_index}")

    # Recreate indexes
    logger.info("Recreating indexes...")
    from scripts.opensearch.create_rag_chunks_index import (
        create_index,
        create_opensearch_client,
    )
    from scripts.opensearch.create_spatial_components_index import (
        create_opensearch_client as create_os_client,
    )
    from scripts.opensearch.create_spatial_components_index import (
        create_spatial_components_index,
    )

    os_client = create_opensearch_client()
    create_index(os_client, delete_if_exists=False)

    spatial_client = create_os_client()
    from app.rag.spatial.schemas import SPATIAL_INDEX_NAME

    create_spatial_components_index(
        spatial_client, SPATIAL_INDEX_NAME, delete_if_exists=False
    )

    logger.success("✓ OpenSearch indexes cleared and recreated")
    logger.info("")


def clear_weaviate_collection():
    """Delete Weaviate Chunk collection"""
    logger.info("=" * 80)
    logger.info("CLEARING WEAVIATE COLLECTION")
    logger.info("=" * 80)

    try:
        if settings.weaviate_use_grpc and settings.weaviate_grpc_port:
            client = weaviate.connect_to_custom(
                http_host=settings.weaviate_host,
                http_port=settings.weaviate_port,
                http_secure=False,
                grpc_host=settings.weaviate_host,
                grpc_port=settings.weaviate_grpc_port,
                grpc_secure=False,
            )
        else:
            client = weaviate.connect_to_local(
                host=settings.weaviate_host,
                port=settings.weaviate_port,
            )

        collection_name = settings.weaviate_collection

        if client.collections.exists(collection_name):
            logger.warning(f"Deleting collection: {collection_name}")
            client.collections.delete(collection_name)
            logger.success(f"✓ Deleted {collection_name} collection")
        else:
            logger.info(f"Collection {collection_name} does not exist (OK)")

        client.close()

    except Exception as e:
        logger.error(f"Failed to clear Weaviate collection: {e}")
        raise

    logger.info("")


def clear_artifacts_directories():
    """Clear artifacts directories"""
    logger.info("=" * 80)
    logger.info("CLEARING ARTIFACTS DIRECTORIES")
    logger.info("=" * 80)

    artifacts_dirs = [
        PROJECT_ROOT / "artifacts" / "ingestion_production",
        PROJECT_ROOT / "artifacts" / "index_production",
    ]

    for artifacts_dir in artifacts_dirs:
        if artifacts_dir.exists():
            logger.warning(f"Deleting directory: {artifacts_dir}")
            try:
                shutil.rmtree(artifacts_dir)
                logger.success(f"✓ Deleted {artifacts_dir}")
            except Exception as e:
                logger.error(f"Failed to delete {artifacts_dir}: {e}")
                raise
        else:
            logger.info(f"Directory {artifacts_dir} does not exist (OK)")

    logger.info("")


def verify_all_cleared():
    """Verify all data has been cleared"""
    logger.info("=" * 80)
    logger.info("VERIFYING ALL DATA CLEARED")
    logger.info("=" * 80)

    # Check OpenSearch
    client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,
    )

    if client.indices.exists(index=settings.opensearch_index):
        count = client.count(index=settings.opensearch_index)["count"]
        if count > 0:
            logger.error(
                f"✗ OpenSearch {settings.opensearch_index} still has {count} documents!"
            )
            return False
        else:
            logger.success(f"✓ OpenSearch {settings.opensearch_index}: 0 documents")
    else:
        logger.error(f"✗ OpenSearch index {settings.opensearch_index} does not exist!")
        return False

    from app.rag.spatial.schemas import SPATIAL_INDEX_NAME

    spatial_index = SPATIAL_INDEX_NAME
    if client.indices.exists(index=spatial_index):
        count = client.count(index=spatial_index)["count"]
        if count > 0:
            logger.warning(
                f"⚠ OpenSearch {spatial_index} has {count} components (OK if no P&ID)"
            )
        else:
            logger.success(f"✓ OpenSearch {spatial_index}: 0 components")
    else:
        logger.error(f"✗ OpenSearch index {spatial_index} does not exist!")
        return False

    # Check Weaviate
    try:
        if settings.weaviate_use_grpc and settings.weaviate_grpc_port:
            wv_client = weaviate.connect_to_custom(
                http_host=settings.weaviate_host,
                http_port=settings.weaviate_port,
                http_secure=False,
                grpc_host=settings.weaviate_host,
                grpc_port=settings.weaviate_grpc_port,
                grpc_secure=False,
            )
        else:
            wv_client = weaviate.connect_to_local(
                host=settings.weaviate_host,
                port=settings.weaviate_port,
            )

        collection_name = settings.weaviate_collection
        if wv_client.collections.exists(collection_name):
            logger.error(f"✗ Weaviate collection {collection_name} still exists!")
            wv_client.close()
            return False
        else:
            logger.success(
                f"✓ Weaviate collection {collection_name} does not exist (cleared)"
            )

        wv_client.close()
    except Exception as e:
        logger.warning(f"⚠ Could not verify Weaviate: {e}")

    # Check artifacts
    artifacts_dirs = [
        PROJECT_ROOT / "artifacts" / "ingestion_production",
        PROJECT_ROOT / "artifacts" / "index_production",
    ]

    for artifacts_dir in artifacts_dirs:
        if artifacts_dir.exists():
            file_count = len(list(artifacts_dir.rglob("*")))
            if file_count > 0:
                logger.warning(
                    f"⚠ {artifacts_dir} still exists with {file_count} items (may be empty dirs)"
                )
            else:
                logger.success(f"✓ {artifacts_dir} cleared")
        else:
            logger.success(f"✓ {artifacts_dir} does not exist (cleared)")

    logger.success("")
    logger.success("✓ ALL DATA CLEARED SUCCESSFULLY")
    logger.success("")
    return True


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Clear all data before re-ingestion")
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip verification after clearing",
    )
    parser.add_argument(
        "--skip-opensearch",
        action="store_true",
        help="Skip clearing OpenSearch indexes",
    )
    parser.add_argument(
        "--skip-weaviate",
        action="store_true",
        help="Skip clearing Weaviate collection",
    )
    parser.add_argument(
        "--skip-artifacts",
        action="store_true",
        help="Skip clearing artifacts directories",
    )

    args = parser.parse_args()

    logger.warning("=" * 80)
    logger.warning("WARNING: THIS WILL DELETE ALL EXISTING DATA!")
    logger.warning("=" * 80)
    logger.warning("")
    logger.warning("This script will:")
    logger.warning("  - Delete OpenSearch indexes (rag_chunks, spatial_components)")
    logger.warning("  - Delete Weaviate collection (Chunk)")
    logger.warning(
        "  - Delete artifacts directories (ingestion_production, index_production)"
    )
    logger.warning("")

    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Aborted.")
        return

    try:
        # Clear OpenSearch
        if not args.skip_opensearch:
            clear_opensearch_indexes()
        else:
            logger.info("Skipping OpenSearch clear")

        # Clear Weaviate
        if not args.skip_weaviate:
            clear_weaviate_collection()
        else:
            logger.info("Skipping Weaviate clear")

        # Clear artifacts
        if not args.skip_artifacts:
            clear_artifacts_directories()
        else:
            logger.info("Skipping artifacts clear")

        # Verify
        if not args.skip_verify:
            if verify_all_cleared():
                logger.success("")
                logger.success("=" * 80)
                logger.success("READY FOR FULL INGESTION")
                logger.success("=" * 80)
                logger.success("")
                logger.success("Next steps:")
                logger.success(
                    "  1. Run: python tools/ingest.py --source-dir D:\\Data_Raw --output-dir artifacts/ingestion_production --enable-ocr --enable-pid-tags"
                )
                logger.success(
                    "  2. Run: python scripts/utilities/index_production_chunks.py"
                )
                logger.success("")
            else:
                logger.error("")
                logger.error("=" * 80)
                logger.error("VERIFICATION FAILED - Some data may not be cleared")
                logger.error("=" * 80)
                logger.error("")
                sys.exit(1)
        else:
            logger.info("Skipping verification")
            logger.success("")
            logger.success("Data cleared (verification skipped)")

    except Exception as e:
        logger.error(f"Error during clearing: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
