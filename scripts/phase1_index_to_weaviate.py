#!/usr/bin/env python
"""
Phase 1: Index documents to Weaviate
=====================================

Reads chunked documents from ingestion output and loads them into Weaviate
with proper metadata (equipment_type, doc_type, equipment_id, vendor).

Usage:
    python scripts/phase1_index_to_weaviate.py --chunks-dir artifacts/ingestion/chunks

Requirements:
    - Weaviate running at http://localhost:8080
    - Chunked documents in JSONL format
    - Embedding service available
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import weaviate
import weaviate.classes as wvc
from loguru import logger
from tqdm import tqdm

from tools.extract_metadata import extract_metadata_from_path, get_extraction_stats


def get_embedding_service():
    """
    Get embedding service based on environment configuration

    Returns:
        Embedding service instance
    """
    from dotenv import load_dotenv

    load_dotenv()

    from app.services.embedding import get_embedding_service as get_svc

    return get_svc()


def ensure_weaviate_schema(client):
    """
    Ensure Weaviate schema exists with correct configuration

    Args:
        client: Weaviate client instance
    """
    try:
        # Check if collection exists
        if client.collections.exists("Chunk"):
            logger.info("Chunk collection already exists")
            # For simplicity, we'll assume it's correct
            # In production, you might want to verify properties
        else:
            logger.info("Creating Chunk collection schema...")
            from weaviate.classes.config import Configure, VectorDistances

            # Use new vector_config API - self_provided for manual vectors (no deprecation)
            client.collections.create(
                name="Chunk",
                vector_config=Configure.Vectors.self_provided(
                    vector_index_config=Configure.VectorIndex.hnsw(
                        distance_metric=VectorDistances.COSINE,
                        ef_construction=128,
                        max_connections=64,
                    ),
                ),
                properties=[
                    wvc.config.Property(
                        name="text", data_type=wvc.config.DataType.TEXT
                    ),
                    wvc.config.Property(
                        name="doc_id", data_type=wvc.config.DataType.TEXT
                    ),
                    wvc.config.Property(name="page", data_type=wvc.config.DataType.INT),
                    wvc.config.Property(
                        name="equipment_type", data_type=wvc.config.DataType.TEXT
                    ),
                    wvc.config.Property(
                        name="doc_type", data_type=wvc.config.DataType.TEXT
                    ),
                    wvc.config.Property(
                        name="equipment_id", data_type=wvc.config.DataType.TEXT
                    ),
                    wvc.config.Property(
                        name="vendor", data_type=wvc.config.DataType.TEXT
                    ),
                    wvc.config.Property(
                        name="source_path", data_type=wvc.config.DataType.TEXT
                    ),
                    wvc.config.Property(
                        name="lang", data_type=wvc.config.DataType.TEXT
                    ),
                ],
            )
            logger.success("Chunk collection created successfully")

    except Exception as e:
        logger.error(f"Failed to ensure schema: {e}")
        raise


def load_chunks_from_jsonl(chunks_dir: Path) -> List[Dict]:
    """
    Load all chunks from JSONL files in chunks directory

    Args:
        chunks_dir: Directory containing chunk JSONL files

    Returns:
        List of chunk dictionaries
    """
    chunks = []
    jsonl_files = list(chunks_dir.glob("*.jsonl"))

    if not jsonl_files:
        logger.warning(f"No JSONL files found in {chunks_dir}")
        return chunks

    logger.info(f"Loading chunks from {len(jsonl_files)} files...")

    for jsonl_file in tqdm(jsonl_files, desc="Loading JSONL files"):
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        chunk = json.loads(line)
                        chunks.append(chunk)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON at {jsonl_file}:{line_num}: {e}")

        except Exception as e:
            logger.error(f"Failed to read {jsonl_file}: {e}")

    logger.success(f"Loaded {len(chunks)} chunks from {len(jsonl_files)} files")
    return chunks


def enrich_chunk_with_metadata(chunk: Dict, doc_id_map: Optional[Dict] = None) -> Dict:
    """
    Enrich chunk with metadata extracted from source path

    Args:
        chunk: Chunk dictionary
        doc_id_map: Optional mapping of doc_id -> source_path

    Returns:
        Enriched chunk dictionary
    """
    # Get source path from doc_id_map or chunk itself
    source_path = None
    doc_id = chunk.get("doc_id")

    if doc_id_map and doc_id:
        source_path = doc_id_map.get(doc_id)

    if not source_path:
        source_path = chunk.get("source_path", "")

    # Extract metadata from path
    if source_path:
        metadata = extract_metadata_from_path(source_path, doc_id=doc_id)

        # Enrich chunk with extracted metadata
        chunk["equipment_type"] = metadata.get("equipment_type", "unknown")
        chunk["doc_type"] = metadata.get("doc_type", "other")
        chunk["equipment_id"] = metadata.get("equipment_id", "")
        chunk["vendor"] = metadata.get("vendor", "")
        chunk["lang"] = metadata.get("lang", "vi")
        chunk["source_path"] = source_path
    else:
        # Set defaults if no source path
        chunk["equipment_type"] = "unknown"
        chunk["doc_type"] = "other"
        chunk["equipment_id"] = ""
        chunk["vendor"] = ""
        chunk["lang"] = "vi"
        chunk["source_path"] = ""

    return chunk


def index_chunks_to_weaviate(
    client,
    chunks: List[Dict],
    embedding_service,
    batch_size: int = 100,
    skip_embedding: bool = False,
) -> Dict:
    """
    Index chunks to Weaviate with embeddings

    Args:
        client: Weaviate client
        chunks: List of chunks to index
        embedding_service: Embedding service instance
        batch_size: Batch size for indexing
        skip_embedding: Skip embedding generation (for testing)

    Returns:
        Indexing statistics
    """
    stats = {
        "total": len(chunks),
        "indexed": 0,
        "failed": 0,
        "skipped": 0,
        "start_time": time.time(),
    }

    logger.info(f"Starting to index {len(chunks)} chunks...")

    # Prepare texts for embedding
    texts = [chunk.get("text", "") for chunk in chunks]

    # Generate embeddings in batches
    if not skip_embedding:
        logger.info("Generating embeddings...")
        try:
            vectors_array = embedding_service.embed_texts(texts)
            # Convert numpy array to list of lists
            vectors = vectors_array.tolist()
            logger.success(f"Generated {len(vectors)} embeddings")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            logger.info("Using zero vectors as fallback...")
            vectors = [[0.0] * 768 for _ in range(len(texts))]
    else:
        logger.warning("Skipping embedding generation (using zero vectors)")
        vectors = [[0.0] * 768 for _ in range(len(texts))]

    # Get collection
    collection = client.collections.get("Chunk")

    # Index in batches using batch context manager
    with collection.batch.dynamic() as batch:
        for idx, (chunk, vector) in enumerate(
            tqdm(zip(chunks, vectors), total=len(chunks), desc="Indexing chunks")
        ):
            try:
                # Prepare properties for Weaviate
                properties = {
                    "text": chunk.get("text", ""),
                    "doc_id": chunk.get("doc_id", ""),
                    "page": chunk.get("page", 0),
                    "equipment_type": chunk.get("equipment_type", "unknown"),
                    "doc_type": chunk.get("doc_type", "other"),
                    "equipment_id": chunk.get("equipment_id", ""),
                    "vendor": chunk.get("vendor", ""),
                    "source_path": chunk.get("source_path", ""),
                    "lang": chunk.get("lang", "vi"),
                }

                # Add to batch
                batch.add_object(properties=properties, vector=vector)

                stats["indexed"] += 1

            except Exception as e:
                logger.warning(f"Failed to index chunk {idx}: {e}")
                stats["failed"] += 1

    stats["end_time"] = time.time()
    stats["duration_seconds"] = stats["end_time"] - stats["start_time"]

    logger.success(
        f"Indexed {stats['indexed']} chunks in {stats['duration_seconds']:.1f}s"
    )
    logger.info(f"Failed: {stats['failed']}, Skipped: {stats['skipped']}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Phase 1: Index documents to Weaviate")
    parser.add_argument(
        "--chunks-dir",
        type=str,
        default="artifacts/ingestion/chunks",
        help="Directory containing chunked documents (JSONL)",
    )
    parser.add_argument(
        "--doc-id-map",
        type=str,
        default="artifacts/ingestion/doc_id_map.json",
        help="Path to doc_id_map.json",
    )
    parser.add_argument(
        "--weaviate-url",
        type=str,
        default="http://localhost:8080",
        help="Weaviate URL",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for indexing",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="Skip embedding generation (use zero vectors for testing)",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing Chunk collection before indexing",
    )

    args = parser.parse_args()

    # Setup paths
    chunks_dir = Path(args.chunks_dir)
    doc_id_map_path = Path(args.doc_id_map)

    if not chunks_dir.exists():
        logger.error(f"Chunks directory not found: {chunks_dir}")
        sys.exit(1)

    # Load doc_id_map if exists
    doc_id_map = {}
    if doc_id_map_path.exists():
        with open(doc_id_map_path, "r", encoding="utf-8") as f:
            doc_id_map = json.load(f)
        logger.info(f"Loaded doc_id_map with {len(doc_id_map)} entries")
    else:
        logger.warning(f"doc_id_map not found: {doc_id_map_path}")

    # Connect to Weaviate
    logger.info(f"Connecting to Weaviate at {args.weaviate_url}...")
    try:
        client = weaviate.connect_to_local(host="localhost", port=8080)
        logger.success("Connected to Weaviate")
    except Exception as e:
        logger.error(f"Failed to connect to Weaviate: {e}")
        sys.exit(1)

    try:
        # Clear existing collection if requested
        if args.clear_existing:
            logger.warning("Clearing existing Chunk collection...")
            try:
                client.collections.delete("Chunk")
                logger.info("Chunk collection deleted")
            except Exception as e:
                logger.warning(f"Failed to delete Chunk collection: {e}")

        # Ensure schema
        ensure_weaviate_schema(client)

        # Load chunks
        chunks = load_chunks_from_jsonl(chunks_dir)

        if not chunks:
            logger.error("No chunks found to index")
            sys.exit(1)

        # Enrich chunks with metadata
        logger.info("Enriching chunks with metadata...")
        enriched_chunks = []
        metadata_list = []

        for chunk in tqdm(chunks, desc="Enriching metadata"):
            enriched_chunk = enrich_chunk_with_metadata(chunk, doc_id_map)
            enriched_chunks.append(enriched_chunk)

            # Track metadata for stats
            metadata_list.append(
                {
                    "equipment_type": enriched_chunk.get("equipment_type"),
                    "doc_type": enriched_chunk.get("doc_type"),
                    "equipment_id": enriched_chunk.get("equipment_id"),
                    "vendor": enriched_chunk.get("vendor"),
                }
            )

        # Show metadata extraction stats
        extraction_stats = get_extraction_stats(metadata_list)
        logger.info("Metadata extraction coverage:")
        for key, value in extraction_stats.items():
            if key == "total":
                logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {key}: {value:.1%}")

        # Initialize embedding service
        embedding_service = None
        if not args.skip_embedding:
            logger.info("Initializing embedding service...")
            embedding_service = get_embedding_service()

        # Index to Weaviate
        index_stats = index_chunks_to_weaviate(
            client=client,
            chunks=enriched_chunks,
            embedding_service=embedding_service,
            batch_size=args.batch_size,
            skip_embedding=args.skip_embedding,
        )

        # Print final summary
        logger.info("=" * 80)
        logger.info("INDEXING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total chunks: {index_stats['total']}")
        logger.info(f"Successfully indexed: {index_stats['indexed']}")
        logger.info(f"Failed: {index_stats['failed']}")
        logger.info(f"Duration: {index_stats['duration_seconds']:.1f}s")
        logger.info("=" * 80)

        # Verify count in Weaviate
        try:
            collection = client.collections.get("Chunk")
            agg = collection.aggregate.over_all(total_count=True)
            count = agg.total_count
            logger.success(f"Total objects in Weaviate Chunk collection: {count}")
        except Exception as e:
            logger.warning(f"Failed to verify count: {e}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
