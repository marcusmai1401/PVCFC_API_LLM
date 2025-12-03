"""Index ingestion chunks to OpenSearch and Weaviate

Usage:
    python tools/index_to_weaviate_opensearch.py --chunks-jsonl artifacts/ingestion/chunks/chunks.jsonl
"""
import argparse
import json
import os
import sys
from pathlib import Path

from loguru import logger

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv()


def load_chunks_from_jsonl(jsonl_file: Path):
    """Load chunks from JSONL file"""
    chunks = []
    logger.info(f"Loading chunks from {jsonl_file}")

    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk = json.loads(line)
                chunks.append(chunk)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON at line {line_num}: {e}")
                continue

    logger.info(f"Loaded {len(chunks)} chunks")
    return chunks


def index_to_opensearch(chunks):
    """Index chunks to OpenSearch"""
    logger.info("=" * 70)
    logger.info("OPENSEARCH INDEXING")
    logger.info("=" * 70)

    try:
        from opensearchpy import OpenSearch
        from opensearchpy.helpers import bulk

        # Get config from env
        host = os.getenv("OPENSEARCH_HOST", "localhost")
        port = int(os.getenv("OPENSEARCH_PORT", "9200"))
        index_name = os.getenv("OPENSEARCH_INDEX", "rag_chunks")

        # Connect (no auth for local)
        client = OpenSearch(
            [{"host": host, "port": port}],
            use_ssl=False,
            verify_certs=False,
            timeout=30,
        )

        logger.info(f"Connected to OpenSearch v{client.info()['version']['number']}")

        # Delete old index if exists
        if client.indices.exists(index=index_name):
            logger.info(f"Deleting existing index: {index_name}")
            client.indices.delete(index=index_name)

        # Create index with mapping
        mapping = {
            "settings": {
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "similarity": {
                        "bm25_custom": {
                            "type": "BM25",
                            "k1": float(os.getenv("OPENSEARCH_BM25_K1", "1.2")),
                            "b": float(os.getenv("OPENSEARCH_BM25_B", "0.75")),
                        }
                    },
                }
            },
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "text": {"type": "text", "similarity": "bm25_custom"},
                    "page_start": {"type": "integer"},
                    "page_end": {"type": "integer"},
                    "page": {"type": "integer"},
                    "chunk_index": {"type": "integer"},
                    "tags": {"type": "keyword"},
                    "tags_raw": {"type": "keyword"},
                    "metadata": {"type": "object", "enabled": True},
                }
            },
        }

        client.indices.create(index=index_name, body=mapping)
        logger.info(f"Created index: {index_name}")

        # Prepare bulk actions
        actions = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})

            actions.append(
                {
                    "_index": index_name,
                    "_id": chunk["chunk_id"],
                    "_source": {
                        "chunk_id": chunk["chunk_id"],
                        "doc_id": chunk["doc_id"],
                        "text": chunk["text"],
                        "page_start": chunk.get("page_start"),
                        "page_end": chunk.get("page_end"),
                        "page": metadata.get("page"),
                        "chunk_index": chunk.get("chunk_index", 0),
                        "tags": metadata.get("tags", []),
                        "tags_raw": metadata.get("tags_raw", []),
                        "metadata": metadata,
                    },
                }
            )

        # Bulk index
        logger.info(f"Bulk indexing {len(actions)} chunks...")
        success, failed = bulk(
            client, actions, raise_on_error=False, request_timeout=60
        )

        if failed:
            logger.warning(f"⚠️  {len(failed)} chunks failed to index")
            for i, error in enumerate(failed[:3]):
                logger.warning(f"Error {i+1}: {error}")

        # Verify count
        client.indices.refresh(index=index_name)
        count = client.count(index=index_name)["count"]

        logger.success(
            f"✅ OpenSearch: {count} chunks indexed (success: {success}, failed: {len(failed)})"
        )

        return True

    except Exception as e:
        logger.error(f"❌ OpenSearch error: {e}")
        import traceback

        traceback.print_exc()
        return False


def index_to_weaviate(chunks):
    """Index chunks to Weaviate"""
    logger.info("\n" + "=" * 70)
    logger.info("WEAVIATE INDEXING")
    logger.info("=" * 70)

    try:
        import weaviate
        import weaviate.classes as wvc

        from app.services.embedding_enhanced import get_embedding_service

        # Get config from env
        host = os.getenv("WEAVIATE_HOST", "localhost")
        port = int(os.getenv("WEAVIATE_PORT", "8080"))
        collection_name = os.getenv("WEAVIATE_COLLECTION", "Chunk")

        # Connect
        client = weaviate.connect_to_local(host=host, port=port)
        logger.info(f"Connected to Weaviate at {host}:{port}")

        # Delete old collection
        if client.collections.exists(collection_name):
            logger.info(f"Deleting existing collection: {collection_name}")
            client.collections.delete(collection_name)

        # Create collection
        logger.info(f"Creating collection: {collection_name}")
        client.collections.create(
            name=collection_name,
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            properties=[
                wvc.config.Property(
                    name="chunk_id", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(name="doc_id", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="chunk_index", data_type=wvc.config.DataType.INT
                ),
                wvc.config.Property(
                    name="page_start", data_type=wvc.config.DataType.INT
                ),
                wvc.config.Property(name="page_end", data_type=wvc.config.DataType.INT),
                wvc.config.Property(name="page", data_type=wvc.config.DataType.INT),
                wvc.config.Property(
                    name="tags", data_type=wvc.config.DataType.TEXT_ARRAY
                ),
                wvc.config.Property(
                    name="tags_raw", data_type=wvc.config.DataType.TEXT_ARRAY
                ),
            ],
        )
        logger.info(f"Collection created")

        # Initialize embedding service
        logger.info("Initializing embedding service...")
        embedding_service = get_embedding_service()

        # Extract texts for embedding
        texts = [chunk["text"] for chunk in chunks]
        logger.info(f"Embedding {len(texts)} chunks...")

        # Embed in batches
        vectors = embedding_service.embed_texts(texts)
        logger.info(f"Embedding complete: {vectors.shape}")

        # Batch insert with vectors
        collection = client.collections.get(collection_name)
        logger.info(f"Batch inserting {len(chunks)} chunks with vectors...")

        batch_size = 100
        with collection.batch.dynamic() as batch:
            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                metadata = chunk.get("metadata", {})

                batch.add_object(
                    properties={
                        "chunk_id": chunk["chunk_id"],
                        "doc_id": chunk["doc_id"],
                        "text": chunk["text"],
                        "chunk_index": chunk.get("chunk_index", 0),
                        "page_start": chunk.get("page_start"),
                        "page_end": chunk.get("page_end"),
                        "page": metadata.get("page"),
                        "tags": metadata.get("tags", []),
                        "tags_raw": metadata.get("tags_raw", []),
                    },
                    vector=vector.tolist(),
                )

                if (i + 1) % 1000 == 0:
                    logger.info(f"  Inserted {i + 1}/{len(chunks)} chunks")

        # Verify count
        result = collection.aggregate.over_all(total_count=True)
        logger.success(f"✅ Weaviate: {result.total_count} chunks indexed")

        client.close()
        return True

    except Exception as e:
        logger.error(f"❌ Weaviate error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Index chunks to Weaviate and OpenSearch"
    )
    parser.add_argument(
        "--chunks-jsonl", type=Path, required=True, help="Path to chunks JSONL file"
    )
    parser.add_argument(
        "--skip-opensearch", action="store_true", help="Skip OpenSearch indexing"
    )
    parser.add_argument(
        "--skip-weaviate", action="store_true", help="Skip Weaviate indexing"
    )

    args = parser.parse_args()

    # Validate input
    if not args.chunks_jsonl.exists():
        logger.error(f"Chunks file not found: {args.chunks_jsonl}")
        sys.exit(1)

    # Load chunks
    chunks = load_chunks_from_jsonl(args.chunks_jsonl)

    if not chunks:
        logger.error("No chunks loaded!")
        sys.exit(1)

    # Index to OpenSearch
    opensearch_success = True
    if not args.skip_opensearch:
        opensearch_success = index_to_opensearch(chunks)
    else:
        logger.info("Skipping OpenSearch indexing")

    # Index to Weaviate
    weaviate_success = True
    if not args.skip_weaviate:
        weaviate_success = index_to_weaviate(chunks)
    else:
        logger.info("Skipping Weaviate indexing")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("INDEXING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"OpenSearch: {'✅ SUCCESS' if opensearch_success else '❌ FAILED'}")
    logger.info(f"Weaviate: {'✅ SUCCESS' if weaviate_success else '❌ FAILED'}")

    if not (opensearch_success and weaviate_success):
        sys.exit(1)


if __name__ == "__main__":
    main()
