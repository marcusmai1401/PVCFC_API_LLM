#!/usr/bin/env python
"""
Update Weaviate Chunk collection with classification properties

This script adds classification-related properties to the existing Chunk collection:
- category (TEXT, filterable) - Document category from taxonomy
- classification_status (TEXT, filterable) - classified | needs_review | pending

Note: doc_type already exists in the schema, so we only add new fields.

Usage:
    python scripts/weaviate/add_classification_properties.py

Requirements:
    pip install weaviate-client>=4.0.0

Note: This adds properties dynamically - no collection recreation required.
Existing objects will have null values for new properties until backfilled.
"""

import sys
from pathlib import Path

from loguru import logger

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import weaviate
    from weaviate.classes.config import DataType, Property
except ImportError:
    logger.error("weaviate-client not installed!")
    logger.error("Run: pip install weaviate-client>=4.0.0")
    sys.exit(1)

from app.core.config import settings

# Collection name
COLLECTION_NAME = "Chunk"

# New classification properties to add
CLASSIFICATION_PROPERTIES = [
    Property(
        name="category",
        data_type=DataType.TEXT,
        description="Document category from taxonomy (ENGINEERING_DESIGN, VENDOR_EQUIPMENT, etc.)",
        index_filterable=True,
        index_searchable=False,
    ),
    Property(
        name="classification_status",
        data_type=DataType.TEXT,
        description="Classification status: classified | needs_review | pending",
        index_filterable=True,
        index_searchable=False,
    ),
]


def connect_to_weaviate() -> weaviate.WeaviateClient:
    """Connect to Weaviate instance"""
    try:
        host = getattr(settings, "weaviate_host", "localhost")
        port = getattr(settings, "weaviate_port", 8080)
        
        client = weaviate.connect_to_local(host=host, port=port)
        
        # Test connection
        if client.is_ready():
            logger.info(f"Connected to Weaviate at {host}:{port}")
            return client
        else:
            logger.error("Weaviate is not ready")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to connect to Weaviate: {e}")
        logger.error("Make sure Weaviate is running: docker-compose up -d weaviate")
        sys.exit(1)


def check_existing_properties(client: weaviate.WeaviateClient) -> list:
    """Get list of existing property names"""
    try:
        collection = client.collections.get(COLLECTION_NAME)
        config = collection.config.get()
        return [p.name for p in config.properties]
    except Exception as e:
        logger.error(f"Failed to get collection config: {e}")
        return []


def add_classification_properties(client: weaviate.WeaviateClient) -> bool:
    """Add classification properties to Chunk collection"""
    try:
        # Check if collection exists
        if not client.collections.exists(COLLECTION_NAME):
            logger.error(f"Collection '{COLLECTION_NAME}' does not exist!")
            logger.error("Create the collection first using create_weaviate_schema.py")
            return False

        # Get existing properties
        existing_props = check_existing_properties(client)
        logger.info(f"Collection '{COLLECTION_NAME}' has {len(existing_props)} properties")
        logger.info(f"Existing properties: {', '.join(existing_props)}")

        # Get collection reference
        collection = client.collections.get(COLLECTION_NAME)

        # Add each new property
        properties_added = []
        properties_skipped = []

        for prop in CLASSIFICATION_PROPERTIES:
            if prop.name in existing_props:
                logger.info(f"  Property '{prop.name}' already exists - skipping")
                properties_skipped.append(prop.name)
            else:
                logger.info(f"  Adding property '{prop.name}'...")
                try:
                    collection.config.add_property(prop)
                    properties_added.append(prop.name)
                    logger.success(f"  ✓ Added '{prop.name}' ({prop.data_type.value})")
                except Exception as e:
                    logger.error(f"  ✗ Failed to add '{prop.name}': {e}")
                    return False

        # Summary
        logger.info("")
        if properties_added:
            logger.success(f"✓ Added {len(properties_added)} new properties: {', '.join(properties_added)}")
        if properties_skipped:
            logger.info(f"ℹ Skipped {len(properties_skipped)} existing properties: {', '.join(properties_skipped)}")

        # Verify final state
        final_props = check_existing_properties(client)
        logger.info(f"\nFinal property count: {len(final_props)}")

        # Check all classification properties exist
        all_present = True
        for prop in CLASSIFICATION_PROPERTIES:
            if prop.name in final_props:
                logger.info(f"  ✓ {prop.name}")
            else:
                logger.error(f"  ✗ {prop.name} - MISSING")
                all_present = False

        # Also check doc_type (should already exist)
        if "doc_type" in final_props:
            logger.info(f"  ✓ doc_type (pre-existing)")
        else:
            logger.warning(f"  ⚠ doc_type not found - may need to add separately")

        return all_present

    except Exception as e:
        logger.error(f"Failed to add properties: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("UPDATE WEAVIATE SCHEMA: Classification Properties")
    logger.info("=" * 80)
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info("Properties to add:")
    for prop in CLASSIFICATION_PROPERTIES:
        logger.info(f"  - {prop.name} ({prop.data_type.value}, filterable={prop.index_filterable})")
    logger.info("=" * 80)

    # Connect to Weaviate
    client = connect_to_weaviate()

    try:
        # Add properties
        success = add_classification_properties(client)

        if success:
            logger.info("=" * 80)
            logger.success("✓ Weaviate schema update completed successfully")
            logger.info("=" * 80)
            logger.info("\nNote: Existing objects will have null values for new properties.")
            logger.info("Run backfill script to populate classification for existing docs.")
            sys.exit(0)
        else:
            logger.error("=" * 80)
            logger.error("✗ Weaviate schema update failed")
            logger.error("=" * 80)
            sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
