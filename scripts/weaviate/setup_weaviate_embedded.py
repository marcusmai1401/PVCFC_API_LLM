#!/usr/bin/env python
"""
Weaviate Embedded Setup - No Docker Required
=============================================

Tạo Weaviate collection với schema cho PVCFC project.
Sử dụng Embedded mode (không cần Docker) cho development/testing.

Usage:
    python setup_weaviate_embedded.py
"""
import sys
from pathlib import Path

from loguru import logger

# Add project root
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import weaviate
    from weaviate.classes.config import Configure, DataType, Property, VectorDistances
except ImportError:
    logger.error("weaviate-client not installed!")
    logger.info("Run: pip install 'weaviate-client[embedded]'")
    sys.exit(1)


def create_chunk_collection(client):
    """
    Create Chunk collection với proper schema.

    Schema bao gồm:
    - text: nội dung chunk
    - doc_id, page, chunk_id: identifiers
    - equipment_type, doc_type, equipment_id, vendor: metadata cho filtering
    - source_path, lang: additional metadata
    """
    logger.info("Creating Chunk collection...")

    try:
        # Check if collection exists
        if client.collections.exists("Chunk"):
            logger.warning("Collection 'Chunk' already exists")
            response = input("Delete and recreate? (y/n): ")
            if response.lower() == "y":
                client.collections.delete("Chunk")
                logger.info("Deleted existing collection")
            else:
                logger.info("Keeping existing collection")
                return

        # Create collection
        client.collections.create(
            name="Chunk",
            # No vectorizer - we provide embeddings from Gemini
            vectorizer_config=Configure.Vectorizer.none(),
            # HNSW index config (optimized for RTX 4060)
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances.COSINE,
                ef_construction=128,  # Build quality
                ef=64,  # Search quality
                max_connections=64,  # Graph connectivity
                dynamic_ef_min=100,  # Dynamic ef range
                dynamic_ef_max=500,
                dynamic_ef_factor=8,
            ),
            # Properties (all indexed by default)
            properties=[
                Property(name="text", data_type=DataType.TEXT),
                Property(name="doc_id", data_type=DataType.TEXT),
                Property(name="page", data_type=DataType.INT),
                Property(name="chunk_id", data_type=DataType.TEXT),
                # Metadata for domain filtering
                Property(name="equipment_type", data_type=DataType.TEXT),
                Property(name="doc_type", data_type=DataType.TEXT),
                Property(name="equipment_id", data_type=DataType.TEXT),
                Property(name="vendor", data_type=DataType.TEXT),
                # Additional metadata
                Property(name="source_path", data_type=DataType.TEXT),
                Property(name="lang", data_type=DataType.TEXT),
            ],
        )

        logger.info("✅ Collection 'Chunk' created successfully!")

        # Verify
        collection = client.collections.get("Chunk")
        config = collection.config.get()

        logger.info(f"Collection config:")
        logger.info(f"  - Vector index: {config.vector_index_type}")
        logger.info(f"  - Distance metric: COSINE")
        logger.info(f"  - Properties: {len(config.properties)} fields")

    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise


def main():
    """Setup Weaviate Embedded with Chunk collection."""

    logger.info("=" * 80)
    logger.info("WEAVIATE EMBEDDED SETUP")
    logger.info("=" * 80)

    # Check if embedded is available
    try:
        from weaviate.embedded import EmbeddedOptions
    except ImportError:
        logger.error("Embedded mode not available!")
        logger.info("Install with: pip install 'weaviate-client[embedded]'")
        return 1

    # Data directories
    data_dir = PROJECT_ROOT / "weaviate_data"
    binary_dir = PROJECT_ROOT / "weaviate_binary"

    data_dir.mkdir(exist_ok=True)
    binary_dir.mkdir(exist_ok=True)

    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Binary directory: {binary_dir}")

    # Start embedded Weaviate
    logger.info("Starting Weaviate Embedded...")
    logger.info("⚠️  First run will download ~100MB binary...")

    try:
        client = weaviate.WeaviateClient(
            embedded_options=EmbeddedOptions(
                persistence_data_path=str(data_dir),
                binary_path=str(binary_dir),
                port=8079,  # Use 8079 to avoid conflict with Docker (8080)
            )
        )

        client.connect()

        # Check if ready
        if client.is_ready():
            logger.info("✅ Weaviate Embedded is ready!")
        else:
            logger.error("❌ Weaviate not ready")
            return 1

        # Create Chunk collection
        create_chunk_collection(client)

        # Show connection info
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ SETUP COMPLETE!")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Weaviate is now running in embedded mode.")
        logger.info("")
        logger.info("Connection info:")
        logger.info("  URL: http://localhost:8079")
        logger.info("  Mode: Embedded (in-process)")
        logger.info("  Collection: Chunk")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Ingest data: python tools/ingest_to_weaviate.py")
        logger.info("  2. Test retrieval: python tools/test_weaviate_retrieval.py")
        logger.info("")
        logger.info("Note: Embedded mode is for development/testing only.")
        logger.info("For production, use Docker Weaviate (docker-compose-weaviate.yml)")
        logger.info("")

        # Close connection
        client.close()
        logger.info("Connection closed.")

        return 0

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
