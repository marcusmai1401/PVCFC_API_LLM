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
    """Main indexing logic with optimized batch processing"""
    import os
    
    logger.info("=" * 80)
    logger.info("INDEXING PRODUCTION CHUNKS (OPTIMIZED BATCH MODE)")
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

    # Read batch size from environment (default 256)
    EMBEDDING_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "256"))
    DB_BATCH_SIZE = BATCH_SIZE  # Keep DB batch size at 100 for stability
    
    logger.info(f"Embedding batch size: {EMBEDDING_BATCH_SIZE}")
    logger.info(f"Database batch size: {DB_BATCH_SIZE}")
    logger.info(f"Concurrency: {os.getenv('EMBED_CONCURRENCY', '8')}")
    logger.info("")

    # Statistics
    stats = {
        "total_chunks": 0,
        "opensearch_indexed": 0,
        "weaviate_indexed": 0,
        "errors": 0,
        "embedding_batches": 0,
    }

    # Count total lines for progress bar
    logger.info("Counting chunks...")
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        total_lines = sum(1 for _ in f)
    logger.info(f"Total chunks to process: {total_lines}")
    logger.info("")

    # Process in batches
    chunk_buffer = []
    opensearch_actions = []
    weaviate_batch_items = []
    
    logger.info("Processing chunks with batch embedding...")
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        with tqdm(total=total_lines, desc="Indexing chunks") as pbar:
            for line_num, line in enumerate(f, 1):
                try:
                    chunk = json.loads(line)
                    chunk_buffer.append(chunk)
                    stats["total_chunks"] += 1
                    pbar.update(1)

                    # When buffer is full or end of file, process batch
                    if len(chunk_buffer) >= EMBEDDING_BATCH_SIZE:
                        _process_embedding_batch(
                            chunk_buffer,
                            embedding_model,
                            opensearch_client,
                            weaviate_collection,
                            opensearch_actions,
                            weaviate_batch_items,
                            stats,
                            DB_BATCH_SIZE,
                        )
                        chunk_buffer = []

                except json.JSONDecodeError as e:
                    logger.error(f"Line {line_num}: JSON decode error: {e}")
                    stats["errors"] += 1
                except Exception as e:
                    logger.error(f"Line {line_num}: Processing error: {e}")
                    stats["errors"] += 1

            # Process remaining chunks in buffer
            if chunk_buffer:
                logger.info(f"Processing final embedding batch ({len(chunk_buffer)} chunks)...")
                _process_embedding_batch(
                    chunk_buffer,
                    embedding_model,
                    opensearch_client,
                    weaviate_collection,
                    opensearch_actions,
                    weaviate_batch_items,
                    stats,
                    DB_BATCH_SIZE,
                )

            # Process remaining DB batches
            if opensearch_actions or weaviate_batch_items:
                logger.info("Flushing final database batches...")
                _flush_db_batches(
                    opensearch_client,
                    weaviate_collection,
                    opensearch_actions,
                    weaviate_batch_items,
                    stats,
                )

    # Refresh OpenSearch index
    logger.info("Refreshing OpenSearch index...")
    opensearch_client.indices.refresh(index=settings.opensearch_index)

    # Close Weaviate connection
    weaviate_client.close()

    # Print statistics
    logger.info("")
    logger.info("=" * 80)
    logger.info("INDEXING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total chunks processed: {stats['total_chunks']}")
    logger.info(f"Embedding batches: {stats['embedding_batches']}")
    logger.info(f"OpenSearch indexed: {stats['opensearch_indexed']}")
    logger.info(f"Weaviate indexed: {stats['weaviate_indexed']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 80)


def _process_embedding_batch(
    chunk_buffer,
    embedding_model,
    opensearch_client,
    weaviate_collection,
    opensearch_actions,
    weaviate_batch_items,
    stats,
    db_batch_size,
):
    """Process a batch of chunks: embed all texts at once, then prepare for DB insertion."""
    if not chunk_buffer:
        return

    try:
        # Step 1: Extract all texts from buffer
        texts = [chunk.get("text", "") for chunk in chunk_buffer]
        
        # Step 2: Embed all texts in ONE API call (uses async internally)
        logger.debug(f"Embedding batch of {len(texts)} chunks...")
        embeddings = embedding_model.embed_texts(texts)  # Returns numpy array (N, dim)
        stats["embedding_batches"] += 1
        
        # Step 3: Map embeddings back to chunks and prepare for DB
        for chunk, embedding in zip(chunk_buffer, embeddings):
            chunk_id = chunk.get("chunk_id")
            text = chunk.get("text", "")
            doc_id = chunk.get("doc_id", "")
            metadata = chunk.get("metadata", {})
            
            # Convert numpy array to list
            embedding_list = embedding.tolist()

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
                "chunk_id": chunk_id,
                "page": metadata.get("page", 1),
                "tags": metadata.get("tags", []),
                "source_path": metadata.get("file_name", ""),
            }

            # Generate deterministic UUID from chunk_id
            uuid = generate_uuid5(chunk_id)

            weaviate_batch_items.append(
                {
                    "uuid": uuid,
                    "chunk_id": chunk_id,
                    "properties": weaviate_properties,
                    "vector": embedding_list,
                }
            )

            # Flush to DB when DB batch is full
            if len(opensearch_actions) >= db_batch_size:
                _flush_db_batches(
                    opensearch_client,
                    weaviate_collection,
                    opensearch_actions,
                    weaviate_batch_items,
                    stats,
                )
                opensearch_actions.clear()
                weaviate_batch_items.clear()

    except Exception as e:
        logger.error(f"Batch embedding failed: {e}", exc_info=True)
        stats["errors"] += len(chunk_buffer)


def _flush_db_batches(
    opensearch_client,
    weaviate_collection,
    opensearch_actions,
    weaviate_batch_items,
    stats,
):
    """Flush accumulated batches to OpenSearch and Weaviate."""
    if not opensearch_actions and not weaviate_batch_items:
        return

    # OpenSearch bulk insert
    if opensearch_actions:
        try:
            success, errors = helpers.bulk(
                opensearch_client,
                opensearch_actions,
                raise_on_error=False,
            )
            stats["opensearch_indexed"] += success
            if errors:
                stats["errors"] += len(errors)
                logger.warning(f"OpenSearch bulk errors: {len(errors)}")
        except Exception as e:
            logger.error(f"OpenSearch bulk insert failed: {e}")
            stats["errors"] += len(opensearch_actions)

    # Weaviate batch insert
    if weaviate_batch_items:
        try:
            with weaviate_collection.batch.fixed_size(
                batch_size=len(weaviate_batch_items)
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
                            f"Weaviate indexing failed for {item['chunk_id']}: {e}"
                        )
                        stats["errors"] += 1
        except Exception as e:
            logger.error(f"Weaviate batch insert failed: {e}")
            stats["errors"] += len(weaviate_batch_items)


if __name__ == "__main__":
    index_chunks()
