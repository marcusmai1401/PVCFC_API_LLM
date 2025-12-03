"""
Script xóa toàn bộ index cũ từ OpenSearch và Weaviate

Xóa:
- OpenSearch: index rag_chunks
- Weaviate: collection Chunk
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger

from app.core.config import settings


def cleanup_opensearch():
    """Xóa toàn bộ OpenSearch index"""
    logger.info("=" * 80)
    logger.info("CLEANING UP OPENSEARCH")
    logger.info("=" * 80)

    try:
        from opensearchpy import OpenSearch

        # Connect
        client = OpenSearch(
            [{"host": settings.opensearch_host, "port": settings.opensearch_port}],
            use_ssl=False,
            verify_certs=False,
            timeout=30,
        )

        version = client.info()["version"]["number"]
        logger.info(f"Connected to OpenSearch v{version}")

        # Get index name
        index_name = settings.opensearch_index

        # Check if index exists
        if client.indices.exists(index=index_name):
            # Get current count
            try:
                count = client.count(index=index_name)["count"]
                logger.warning(f"Index '{index_name}' contains {count} documents")
            except:
                logger.warning(f"Index '{index_name}' exists")

            # Confirm deletion
            logger.warning(f"⚠️  About to DELETE index: {index_name}")
            response = input("Are you sure? (yes/no): ")

            if response.lower() == "yes":
                client.indices.delete(index=index_name)
                logger.success(f"✅ Deleted OpenSearch index: {index_name}")
                return True
            else:
                logger.info("Cancelled by user")
                return False
        else:
            logger.info(f"Index '{index_name}' does not exist (already clean)")
            return True

    except Exception as e:
        logger.error(f"❌ OpenSearch cleanup error: {e}")
        import traceback

        traceback.print_exc()
        return False


def cleanup_weaviate():
    """Xóa toàn bộ Weaviate collection"""
    logger.info("\n" + "=" * 80)
    logger.info("CLEANING UP WEAVIATE")
    logger.info("=" * 80)

    try:
        import weaviate

        # Connect
        host = settings.weaviate_host
        port = settings.weaviate_port
        collection_name = settings.weaviate_collection

        client = weaviate.connect_to_local(host=host, port=port)
        logger.info(f"Connected to Weaviate at {host}:{port}")

        # Check if collection exists
        if client.collections.exists(collection_name):
            # Get count
            try:
                collection = client.collections.get(collection_name)
                result = collection.aggregate.over_all(total_count=True)
                count = result.total_count
                logger.warning(
                    f"Collection '{collection_name}' contains {count} objects"
                )
            except:
                logger.warning(f"Collection '{collection_name}' exists")

            # Confirm deletion
            logger.warning(f"⚠️  About to DELETE collection: {collection_name}")
            response = input("Are you sure? (yes/no): ")

            if response.lower() == "yes":
                client.collections.delete(collection_name)
                logger.success(f"✅ Deleted Weaviate collection: {collection_name}")
                client.close()
                return True
            else:
                logger.info("Cancelled by user")
                client.close()
                return False
        else:
            logger.info(
                f"Collection '{collection_name}' does not exist (already clean)"
            )
            client.close()
            return True

    except Exception as e:
        logger.error(f"❌ Weaviate cleanup error: {e}")
        import traceback

        traceback.print_exc()
        return False


def cleanup_all():
    """Xóa toàn bộ indexes"""
    logger.info("\n" + "=" * 80)
    logger.info("CLEANUP ALL INDEXES")
    logger.info("=" * 80)
    logger.warning("This will DELETE all indexed data from:")
    logger.warning(f"  - OpenSearch index: {settings.opensearch_index}")
    logger.warning(f"  - Weaviate collection: {settings.weaviate_collection}")
    logger.warning("")

    # Cleanup OpenSearch
    os_success = cleanup_opensearch()

    # Cleanup Weaviate
    wv_success = cleanup_weaviate()

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 80)
    logger.info(f"OpenSearch: {'✅ Cleaned' if os_success else '❌ Failed'}")
    logger.info(f"Weaviate: {'✅ Cleaned' if wv_success else '❌ Failed'}")

    if os_success and wv_success:
        logger.success("\n✅ ALL INDEXES CLEANED SUCCESSFULLY")
        logger.info("You can now re-index with correct mapping")
    else:
        logger.error("\n❌ CLEANUP INCOMPLETE")


if __name__ == "__main__":
    cleanup_all()
