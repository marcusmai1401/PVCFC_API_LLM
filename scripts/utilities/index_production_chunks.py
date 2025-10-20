"""Index production chunks into OpenSearch and Weaviate

Reads from artifacts/ingestion_production/chunks/chunks.jsonl and indexes to both systems.
"""
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import weaviate
from loguru import logger
from opensearchpy import OpenSearch, helpers
from tqdm import tqdm
from weaviate.util import generate_uuid5

from app.core.config import settings
from app.services.embedding_enhanced import UniversalEmbeddingService

# Configuration
CHUNKS_FILE = (
    PROJECT_ROOT / "artifacts" / "ingestion_production" / "chunks" / "chunks.jsonl"
)
BATCH_SIZE = 100


def load_embedding_model():
    """Load the embedding model"""
    logger.info("Loading embedding model...")
    logger.info(f"Provider: {settings.embedding_provider}")
    logger.info(f"Model: {settings.embedding_model}")

    # Use UniversalEmbeddingService which respects config
    embedding_service = UniversalEmbeddingService(
        provider=settings.embedding_provider, model_name=settings.embedding_model
    )

    logger.success(
        f"✅ Embedding model loaded: {settings.embedding_provider}/{settings.embedding_model}"
    )
    return embedding_service


def connect_opensearch():
    """Connect to OpenSearch"""
    logger.info("Connecting to OpenSearch...")
    client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,
    )

    # Verify index exists
    if not client.indices.exists(index=settings.opensearch_index):
        logger.error(f"OpenSearch index '{settings.opensearch_index}' does not exist!")
        logger.error("Please run: python scripts/opensearch/create_rag_chunks_index.py")
        sys.exit(1)

    logger.success(f"✅ OpenSearch connected: index={settings.opensearch_index}")
    return client


def connect_weaviate():
    """Connect to Weaviate"""
    logger.info("Connecting to Weaviate...")

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
    logger.success(f"✅ Weaviate connected: collection={settings.weaviate_collection}")
    return client, collection


def index_chunks():
    """Main indexing logic"""
    logger.info("=" * 80)
    logger.info("INDEXING PRODUCTION CHUNKS")
    logger.info("=" * 80)
    logger.info(f"Chunks file: {CHUNKS_FILE}")
    logger.info("")

    if not CHUNKS_FILE.exists():
        logger.error(f"Chunks file not found: {CHUNKS_FILE}")
        sys.exit(1)

    # Connect to services
    embedding_model = load_embedding_model()
    opensearch_client = connect_opensearch()
    weaviate_client, weaviate_collection = connect_weaviate()

    # Statistics
    stats = {
        "total_chunks": 0,
        "opensearch_indexed": 0,
        "weaviate_indexed": 0,
        "errors": 0,
    }

    # Prepare batches
    opensearch_actions = []
    weaviate_batch_items = []

    logger.info("Processing chunks...")
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(tqdm(f, desc="Indexing chunks"), 1):
            try:
                chunk = json.loads(line)
                stats["total_chunks"] += 1

                chunk_id = chunk.get("chunk_id")
                text = chunk.get("text", "")
                doc_id = chunk.get("doc_id", "")
                metadata = chunk.get("metadata", {})

                # Generate embedding using UniversalEmbeddingService
                embedding = embedding_model.embed_texts([text], batch_size=1)[
                    0
                ].tolist()

                # Prepare OpenSearch document
                os_doc = {
                    "text": text,
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "chunk_index": chunk.get("chunk_index", 0),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "page": metadata.get("page"),
                    "doc_type": metadata.get("doc_type"),
                    "revision": metadata.get("revision"),
                    "file_name": metadata.get("file_name"),
                    "source_format": metadata.get("source_format"),
                    "tags": metadata.get("tags", []),
                    "tags_raw": metadata.get("tags_raw", []),
                }

                # Remove None values
                os_doc = {k: v for k, v in os_doc.items() if v is not None}

                opensearch_actions.append(
                    {
                        "_op_type": "index",
                        "_index": settings.opensearch_index,
                        "_id": chunk_id,
                        "_source": os_doc,
                    }
                )

                # Prepare Weaviate object
                weaviate_properties = {
                    "text": text,
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,  # Add chunk_id to properties
                    "page": metadata.get("page", 1),
                    "tags": metadata.get("tags", []),
                    "source_path": metadata.get("file_name", ""),
                }

                # Generate deterministic UUID from chunk_id
                uuid = generate_uuid5(chunk_id)

                weaviate_batch_items.append(
                    {
                        "uuid": uuid,
                        "chunk_id": chunk_id,  # Store original chunk_id
                        "properties": weaviate_properties,
                        "vector": embedding,
                    }
                )

                # Batch insert when ready
                if len(opensearch_actions) >= BATCH_SIZE:
                    # OpenSearch bulk insert
                    success, errors = helpers.bulk(
                        opensearch_client,
                        opensearch_actions,
                        raise_on_error=False,
                    )
                    stats["opensearch_indexed"] += success
                    if errors:
                        stats["errors"] += len(errors)

                    # Weaviate batch insert
                    with weaviate_collection.batch.fixed_size(
                        batch_size=BATCH_SIZE
                    ) as batch:
                        for item in weaviate_batch_items:
                            try:
                                batch.add_object(
                                    uuid=item["uuid"],
                                    properties=item["properties"],
                                    vector=item["vector"],
                                )
                                stats["weaviate_indexed"] += 1
                            except Exception as e:
                                logger.warning(
                                    f"Weaviate indexing failed for {item['uuid']}: {e}"
                                )
                                stats["errors"] += 1

                    # Reset batches
                    opensearch_actions = []
                    weaviate_batch_items = []

            except json.JSONDecodeError as e:
                logger.error(f"Line {line_num}: JSON decode error: {e}")
                stats["errors"] += 1
            except Exception as e:
                logger.error(f"Line {line_num}: Processing error: {e}")
                stats["errors"] += 1

    # Process remaining batches
    if opensearch_actions:
        logger.info("Processing final batch...")
        success, errors = helpers.bulk(
            opensearch_client,
            opensearch_actions,
            raise_on_error=False,
        )
        stats["opensearch_indexed"] += success
        if errors:
            stats["errors"] += len(errors)

        with weaviate_collection.batch.fixed_size(batch_size=BATCH_SIZE) as batch:
            for item in weaviate_batch_items:
                try:
                    batch.add_object(
                        uuid=item["uuid"],
                        properties=item["properties"],
                        vector=item["vector"],
                    )
                    stats["weaviate_indexed"] += 1
                except Exception as e:
                    logger.warning(f"Weaviate indexing failed for {item['uuid']}: {e}")
                    stats["errors"] += 1

    # Refresh OpenSearch index
    opensearch_client.indices.refresh(index=settings.opensearch_index)

    # Close Weaviate connection
    weaviate_client.close()

    # Print statistics
    logger.info("")
    logger.info("=" * 80)
    logger.info("INDEXING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total chunks processed: {stats['total_chunks']}")
    logger.info(f"OpenSearch indexed: {stats['opensearch_indexed']}")
    logger.info(f"Weaviate indexed: {stats['weaviate_indexed']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 80)


if __name__ == "__main__":
    index_chunks()
