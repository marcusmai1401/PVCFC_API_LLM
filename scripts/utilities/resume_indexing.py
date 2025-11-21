"""Resume indexing for Weaviate by skipping existing objects.

This script:
1. Connects to Weaviate.
2. Fetches ALL existing UUIDs into memory (efficient set).
3. Iterates through chunks.jsonl.
4. Skips chunks that are already in Weaviate.
5. Embeds and indexes only the missing chunks.
"""
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import weaviate
from loguru import logger
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
    logger.info("Loading embedding model...")
    return UniversalEmbeddingService(
        provider=settings.embedding_provider, model_name=settings.embedding_model
    )

def connect_weaviate():
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
    return client, collection

def get_existing_uuids(collection):
    """Fetch all existing UUIDs using iterator"""
    logger.info("Fetching existing UUIDs from Weaviate to check progress...")
    existing_uuids = set()
    try:
        # Using iterator to fetch all IDs efficiently
        for item in tqdm(collection.iterator(include_vector=False), desc="Checking existing data"):
            existing_uuids.add(str(item.uuid))
    except Exception as e:
        logger.warning(f"Could not fetch existing UUIDs: {e}")
        return set()
    
    logger.success(f"✅ Found {len(existing_uuids)} objects already in Weaviate.")
    return existing_uuids

def resume_indexing():
    if not CHUNKS_FILE.exists():
        logger.error(f"Chunks file not found: {CHUNKS_FILE}")
        sys.exit(1)

    embedding_model = load_embedding_model()
    client, collection = connect_weaviate()
    
    # 1. Get existing state
    existing_uuids = get_existing_uuids(collection)
    
    stats = {
        "total_chunks": 0,
        "skipped": 0,
        "indexed": 0,
        "errors": 0
    }
    
    batch_items = []
    
    logger.info("Scanning chunks.jsonl...")
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Processing chunks"):
            try:
                chunk = json.loads(line)
                stats["total_chunks"] += 1
                
                chunk_id = chunk.get("chunk_id")
                uuid = str(generate_uuid5(chunk_id))
                
                # 2. Check overlap
                if uuid in existing_uuids:
                    stats["skipped"] += 1
                    continue
                
                # 3. Process missing chunk
                text = chunk.get("text", "")
                doc_id = chunk.get("doc_id", "")
                metadata = chunk.get("metadata", {})
                
                # Embed
                embedding = embedding_model.embed_texts([text], batch_size=1)[0].tolist()
                
                weaviate_properties = {
                    "text": text,
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "page": metadata.get("page", 1),
                    "tags": metadata.get("tags", []),
                    "source_path": metadata.get("file_name", ""),
                }
                
                batch_items.append({
                    "uuid": uuid,
                    "properties": weaviate_properties,
                    "vector": embedding
                })
                
                # Batch insert
                if len(batch_items) >= BATCH_SIZE:
                    with collection.batch.fixed_size(batch_size=BATCH_SIZE) as batch:
                        for item in batch_items:
                            batch.add_object(
                                uuid=item["uuid"],
                                properties=item["properties"],
                                vector=item["vector"]
                            )
                    stats["indexed"] += len(batch_items)
                    batch_items = []
                    
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error processing chunk: {e}")

    # Final batch
    if batch_items:
        with collection.batch.fixed_size(batch_size=BATCH_SIZE) as batch:
            for item in batch_items:
                batch.add_object(
                    uuid=item["uuid"],
                    properties=item["properties"],
                    vector=item["vector"]
                )
        stats["indexed"] += len(batch_items)

    client.close()
    
    logger.info("=" * 80)
    logger.info("RESUME COMPLETE")
    logger.info(f"Total chunks in file: {stats['total_chunks']}")
    logger.info(f"Already existed (Skipped): {stats['skipped']}")
    logger.info(f"Newly Indexed: {stats['indexed']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 80)

if __name__ == "__main__":
    resume_indexing()
