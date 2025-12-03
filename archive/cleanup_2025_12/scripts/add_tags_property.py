"""
Add Tags Property to Weaviate Chunk Collection

One-time schema migration to add tags property (TEXT_ARRAY)
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import weaviate
from loguru import logger
from weaviate.classes.config import DataType, Property

from app.core.config import settings


def add_tags_property():
    """Add tags property to Weaviate Chunk collection"""

    logger.info("=" * 80)
    logger.info("UPDATING WEAVIATE SCHEMA: Adding tags property")
    logger.info("=" * 80)

    try:
        # Connect to Weaviate
        logger.info(
            f"Connecting to Weaviate at {settings.weaviate_host}:{settings.weaviate_port}"
        )

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

        logger.info("✅ Connected to Weaviate")

        # Get collection
        collection_name = settings.weaviate_collection
        collection = client.collections.get(collection_name)

        logger.info(f"Collection: {collection_name}")

        # Check current properties
        config = collection.config.get()
        current_props = [p.name for p in config.properties]

        logger.info(f"Current properties ({len(current_props)}): {current_props}")

        # Check if tags property already exists
        if "tags" in current_props:
            logger.warning("⚠️  Property 'tags' already exists")
            response = input("Skip or recreate? (skip/recreate): ")
            if response.lower() != "recreate":
                logger.info("Skipping tags property addition")
                client.close()
                return True

        # Add tags property
        logger.info("Adding 'tags' property (TEXT_ARRAY)...")

        collection.config.add_property(
            Property(
                name="tags",
                data_type=DataType.TEXT_ARRAY,
                description="Equipment tags extracted from chunk (e.g., ['E04217', 'P04201A'])",
            )
        )

        logger.info("✅ Successfully added 'tags' property to Weaviate schema")
        logger.info("")
        logger.info("Property details:")
        logger.info("  - Name: tags")
        logger.info("  - Type: TEXT_ARRAY")
        logger.info("  - Description: Equipment tags extracted from chunk")
        logger.info("")
        logger.info("Note: Existing data will not have tags until backfill")

        client.close()
        return True

    except Exception as e:
        logger.error(f"❌ Failed to add tags property: {e}")
        logger.exception(e)
        return False


if __name__ == "__main__":
    success = add_tags_property()
    sys.exit(0 if success else 1)
