"""Clean all indexed data from OpenSearch and Weaviate before re-indexing

This script safely deletes all data from:
- OpenSearch: rag_chunks index
- OpenSearch: pvcfc_pid_spatial_components index (if exists)
- Weaviate: Chunk collection

Use this before running a fresh indexing cycle.
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import weaviate
from loguru import logger
from opensearchpy import OpenSearch

from app.core.config import settings


def clean_opensearch():
    """Delete all documents from OpenSearch indices"""
    logger.info("=" * 80)
    logger.info("CLEANING OPENSEARCH INDICES")
    logger.info("=" * 80)

    try:
        client = OpenSearch(
            hosts=[
                {"host": settings.opensearch_host, "port": settings.opensearch_port}
            ],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            timeout=60,
        )

        # Check if indices exist
        indices_to_clean = [
            settings.opensearch_index,  # rag_chunks
            "pvcfc_pid_spatial_components",  # P&ID spatial components
        ]

        for index_name in indices_to_clean:
            if client.indices.exists(index=index_name):
                # Get document count before deletion
                count_response = client.count(index=index_name)
                doc_count = count_response.get("count", 0)

                logger.info(f"Index '{index_name}': {doc_count} documents")

                if doc_count > 0:
                    # Delete all documents (keep index structure)
                    response = client.delete_by_query(
                        index=index_name,
                        body={"query": {"match_all": {}}},
                        conflicts="proceed",
                        refresh=True,
                    )

                    deleted = response.get("deleted", 0)
                    logger.success(f"✅ Deleted {deleted} documents from '{index_name}'")
                else:
                    logger.info(f"Index '{index_name}' is already empty")
            else:
                logger.warning(f"Index '{index_name}' does not exist, skipping")

        logger.success("✅ OpenSearch cleanup complete")
        return True

    except Exception as e:
        logger.error(f"❌ OpenSearch cleanup failed: {e}")
        return False


def clean_weaviate():
    """Delete all objects from Weaviate collection"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("CLEANING WEAVIATE COLLECTION")
    logger.info("=" * 80)

    try:
        # Connect to Weaviate
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

        collection = client.collections.get(settings.weaviate_collection)

        # Get object count before deletion
        try:
            # Try to get aggregate count
            response = collection.aggregate.over_all(total_count=True)
            object_count = response.total_count if response else 0
        except:
            # Fallback: try to estimate from query
            try:
                result = collection.query.fetch_objects(limit=1)
                # If we can fetch, there are objects
                object_count = "unknown (non-zero)"
            except:
                object_count = 0

        logger.info(
            f"Collection '{settings.weaviate_collection}': {object_count} objects"
        )

        if object_count != 0:
            # Delete all objects from collection
            logger.info("Deleting all objects (this may take a while)...")

            # Method 1: Try batch delete with iterator (recommended for large collections)
            try:
                deleted_count = 0
                # Iterate and delete in batches
                for item in collection.iterator(include_vector=False):
                    collection.data.delete_by_id(item.uuid)
                    deleted_count += 1
                    if deleted_count % 1000 == 0:
                        logger.info(f"Deleted {deleted_count} objects...")

                logger.success(
                    f"✅ Deleted {deleted_count} objects from '{settings.weaviate_collection}'"
                )
            except Exception as e:
                # Method 2: Fallback - delete collection and recreate
                logger.warning(f"Batch delete failed: {e}")
                logger.info(
                    "Trying alternative method: delete and recreate collection..."
                )

                # Get collection schema before deletion
                try:
                    # Delete entire collection
                    client.collections.delete(settings.weaviate_collection)
                    logger.info(f"Deleted collection '{settings.weaviate_collection}'")

                    # Recreate empty collection with same schema
                    from weaviate.classes.config import DataType, Property

                    client.collections.create(
                        name=settings.weaviate_collection,
                        properties=[
                            Property(name="text", data_type=DataType.TEXT),
                            Property(name="doc_id", data_type=DataType.TEXT),
                            Property(name="chunk_id", data_type=DataType.TEXT),
                            Property(name="page", data_type=DataType.INT),
                            Property(name="tags", data_type=DataType.TEXT_ARRAY),
                            Property(name="source_path", data_type=DataType.TEXT),
                        ],
                    )
                    logger.success(
                        f"✅ Recreated empty collection '{settings.weaviate_collection}'"
                    )
                except Exception as e2:
                    logger.error(f"Failed to recreate collection: {e2}")
                    raise
        else:
            logger.info(f"Collection '{settings.weaviate_collection}' is already empty")

        # Close connection
        client.close()

        logger.success("✅ Weaviate cleanup complete")
        return True

    except Exception as e:
        logger.error(f"❌ Weaviate cleanup failed: {e}")
        return False


def main():
    """Main cleanup function"""
    logger.info("")
    logger.info("🧹 " + "=" * 76)
    logger.info("CLEANING ALL INDEXED DATA")
    logger.info("=" * 80)
    logger.info("")
    logger.warning(
        "⚠️  This will delete ALL indexed data from OpenSearch and Weaviate!"
    )
    logger.warning("⚠️  Source data (chunks.jsonl) will NOT be affected.")
    logger.info("")

    # Ask for confirmation
    try:
        response = input("Type 'YES' to proceed with cleanup: ")
        if response.strip().upper() != "YES":
            logger.info("Cleanup cancelled by user")
            return
    except KeyboardInterrupt:
        logger.info("\nCleanup cancelled by user")
        return

    logger.info("")
    logger.info("Starting cleanup...")
    logger.info("")

    # Clean OpenSearch
    opensearch_success = clean_opensearch()

    # Clean Weaviate
    weaviate_success = clean_weaviate()

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 80)
    logger.info(f"OpenSearch: {'✅ SUCCESS' if opensearch_success else '❌ FAILED'}")
    logger.info(f"Weaviate: {'✅ SUCCESS' if weaviate_success else '❌ FAILED'}")
    logger.info("=" * 80)

    if opensearch_success and weaviate_success:
        logger.success("")
        logger.success("🎉 All indices cleaned successfully!")
        logger.success(
            "You can now run: python scripts/utilities/index_production_chunks.py"
        )
        logger.success("")
    else:
        logger.error("")
        logger.error("⚠️  Some cleanup operations failed. Check logs above.")
        logger.error("")


if __name__ == "__main__":
    main()
