#!/usr/bin/env python
"""
Update OpenSearch rag_chunks index mapping for classification metadata

This script adds classification-related fields to the existing rag_chunks index:
- metadata.category (keyword) - Document category from taxonomy
- metadata.doc_type (keyword) - Specific document type within category  
- metadata.classification_status (keyword) - classified | needs_review | pending
- metadata.classification_confidence (float) - AI confidence score 0.0-1.0
- metadata.classification_method (keyword) - cadlike_gate | ai_classifier | manual

Usage:
    python scripts/opensearch/update_classification_mapping.py

Requirements:
    pip install opensearch-py

Note: This uses dynamic mapping update - no reindex required for existing documents.
Existing documents will have null values for new fields until backfilled.
"""

import sys
from pathlib import Path

from loguru import logger
from opensearchpy import OpenSearch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Index configuration
INDEX_NAME = "rag_chunks"
OS_HOST = "localhost"
OS_PORT = 9200

# New classification metadata fields to add
CLASSIFICATION_MAPPING_UPDATE = {
    "properties": {
        "category": {
            "type": "keyword",
            "doc_values": True,
        },
        "classification_status": {
            "type": "keyword",
            "doc_values": True,
        },
        "classification_confidence": {
            "type": "float",
        },
        "classification_method": {
            "type": "keyword",
            "doc_values": True,
        },
    }
}


def create_opensearch_client() -> OpenSearch:
    """Create OpenSearch client connection"""
    import os

    host = os.environ.get("OPENSEARCH_HOST", OS_HOST)
    port = int(os.environ.get("OPENSEARCH_PORT", OS_PORT))

    try:
        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
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
        logger.error(f"Failed to connect to OpenSearch at {host}:{port}")
        logger.error(f"Error: {e}")
        logger.error("Make sure OpenSearch is running: docker-compose up -d opensearch")
        sys.exit(1)


def check_existing_mapping(client: OpenSearch) -> dict:
    """Check current index mapping"""
    try:
        mapping = client.indices.get_mapping(index=INDEX_NAME)
        props = mapping[INDEX_NAME]["mappings"]["properties"]
        return props
    except Exception as e:
        logger.error(f"Failed to get mapping: {e}")
        return {}


def update_mapping(client: OpenSearch) -> bool:
    """Update index mapping with classification fields"""
    try:
        # Check if index exists
        if not client.indices.exists(index=INDEX_NAME):
            logger.error(f"Index '{INDEX_NAME}' does not exist!")
            logger.error("Run create_rag_chunks_index.py first to create the index.")
            return False

        # Get current mapping
        current_props = check_existing_mapping(client)
        logger.info(f"Current mapping has {len(current_props)} fields")

        # Check which fields already exist
        new_fields = CLASSIFICATION_MAPPING_UPDATE["properties"]
        fields_to_add = {}
        fields_existing = []

        for field_name, field_config in new_fields.items():
            if field_name in current_props:
                fields_existing.append(field_name)
                logger.info(f"  Field '{field_name}' already exists - skipping")
            else:
                fields_to_add[field_name] = field_config
                logger.info(f"  Field '{field_name}' will be added")

        if not fields_to_add:
            logger.info("All classification fields already exist. No update needed.")
            return True

        # Update mapping with new fields
        logger.info(f"\nAdding {len(fields_to_add)} new fields to mapping...")
        
        update_body = {"properties": fields_to_add}
        response = client.indices.put_mapping(index=INDEX_NAME, body=update_body)

        if response.get("acknowledged"):
            logger.success(f"✓ Successfully added classification fields to '{INDEX_NAME}'")
            
            # Verify update
            updated_props = check_existing_mapping(client)
            logger.info(f"\nUpdated mapping now has {len(updated_props)} fields")
            
            # List new fields
            logger.info("\nNew classification fields added:")
            for field_name in fields_to_add:
                if field_name in updated_props:
                    logger.info(f"  ✓ {field_name}: {updated_props[field_name]['type']}")
                else:
                    logger.warning(f"  ✗ {field_name}: NOT FOUND (unexpected)")
            
            return True
        else:
            logger.error("Mapping update not acknowledged")
            return False

    except Exception as e:
        logger.error(f"Failed to update mapping: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("UPDATE OPENSEARCH MAPPING: Classification Metadata Fields")
    logger.info("=" * 80)
    logger.info(f"Index: {INDEX_NAME}")
    logger.info("Fields to add:")
    for field_name, field_config in CLASSIFICATION_MAPPING_UPDATE["properties"].items():
        logger.info(f"  - {field_name} ({field_config['type']})")
    logger.info("=" * 80)

    # Create client
    client = create_opensearch_client()

    # Update mapping
    success = update_mapping(client)

    if success:
        logger.info("=" * 80)
        logger.success("✓ OpenSearch mapping update completed successfully")
        logger.info("=" * 80)
        logger.info("\nNote: Existing documents will have null values for new fields.")
        logger.info("Run backfill script to populate classification for existing docs.")
        sys.exit(0)
    else:
        logger.error("=" * 80)
        logger.error("✗ OpenSearch mapping update failed")
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
