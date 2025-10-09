"""
Safe script to build BM25 and FAISS indices with validation
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from loguru import logger

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.indexers.bm25_indexer import BM25Indexer
from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding_enhanced import get_embedding_service


def load_chunks_from_dir(chunks_dir: Path):
    """Load all chunks from JSON files in directory"""
    logger.info(f"Loading chunks from {chunks_dir}")

    all_chunks = []
    chunk_files = list(chunks_dir.glob("*_chunks.json"))

    if not chunk_files:
        logger.error(f"No chunk files found in {chunks_dir}")
        return []

    logger.info(f"Found {len(chunk_files)} chunk files")

    for i, chunk_file in enumerate(chunk_files, 1):
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
                all_chunks.extend(chunks)

            if i % 10 == 0:
                logger.info(
                    f"Loaded {i}/{len(chunk_files)} files ({len(all_chunks)} chunks so far)"
                )
        except Exception as e:
            logger.error(f"Failed to load {chunk_file.name}: {e}")

    logger.info(
        f"✓ Loaded {len(all_chunks)} total chunks from {len(chunk_files)} files"
    )
    return all_chunks


def validate_chunks(chunks):
    """Validate chunk structure"""
    logger.info("Validating chunks...")

    if not chunks:
        logger.error("No chunks to validate")
        return False

    # Check required fields
    required_fields = ["text", "doc_id", "chunk_id"]
    sample = chunks[0]

    missing = [f for f in required_fields if f not in sample]
    if missing:
        logger.error(f"Missing required fields: {missing}")
        return False

    # Check for high page numbers (verify our fix worked)
    high_page_chunks = []
    for chunk in chunks:
        page_end = chunk.get("page_end", 0)
        if page_end > 500:
            high_page_chunks.append((chunk.get("doc_id", "Unknown")[:50], page_end))

    if high_page_chunks:
        max_page = max(p[1] for p in high_page_chunks)
        logger.info(f"✓ Found {len(high_page_chunks)} chunks with high page numbers")
        logger.info(f"✓ Max page number: {max_page}")
    else:
        logger.warning("No chunks with page > 500 found (expected for large manuals)")

    logger.info("✓ Chunk validation passed")
    return True


def build_bm25_index(chunks, output_dir: Path):
    """Build BM25 index"""
    logger.info("=" * 80)
    logger.info("BUILDING BM25 INDEX")
    logger.info("=" * 80)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize indexer
    indexer = BM25Indexer()

    # Build index
    logger.info(f"Indexing {len(chunks)} chunks...")
    start_time = datetime.now()
    indexer.build_index(chunks)
    elapsed = (datetime.now() - start_time).total_seconds()

    # Save index
    logger.info(f"Saving index to {output_dir}")
    indexer.save_index(str(output_dir))

    logger.info(f"✓ BM25 index built in {elapsed:.1f}s")
    return indexer


def build_faiss_index(chunks, output_dir: Path, embedding_service):
    """Build FAISS vector index"""
    logger.info("=" * 80)
    logger.info("BUILDING FAISS INDEX")
    logger.info("=" * 80)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract texts and metadata
    texts = [chunk["text"] for chunk in chunks]
    metadatas = [chunk.get("metadata", {}) for chunk in chunks]

    # Embed chunks in batches
    logger.info(f"Embedding {len(chunks)} chunks...")
    logger.info("⚠️  This will take 10-20 minutes depending on chunk count...")

    embeddings_list = []
    batch_size = 100
    total_batches = (len(texts) + batch_size - 1) // batch_size

    start_time = datetime.now()

    for i in range(0, len(texts), batch_size):
        batch_end = min(i + batch_size, len(texts))
        batch_texts = texts[i:batch_end]
        batch_num = i // batch_size + 1

        logger.info(
            f"Embedding batch {batch_num}/{total_batches} [{i+1}-{batch_end}/{len(texts)}]"
        )

        # Embed batch
        batch_embeddings = embedding_service.embed_texts(batch_texts)
        embeddings_list.append(batch_embeddings)

        # Show progress estimate
        if batch_num % 10 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = batch_num / elapsed
            remaining = (total_batches - batch_num) / rate
            logger.info(
                f"  Progress: {batch_num}/{total_batches} ({100*batch_num/total_batches:.1f}%) - ETA: {remaining/60:.1f} min"
            )

    # Concatenate embeddings
    logger.info("Concatenating embeddings...")
    embeddings = np.vstack(embeddings_list)

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"✓ Embedding completed in {elapsed/60:.1f} minutes")

    # Build FAISS index
    logger.info(
        f"Building FAISS index with {len(embeddings)} vectors (dim={embeddings.shape[1]})..."
    )
    indexer = VectorIndexer()
    indexer.build(embeddings, texts, metadatas)

    # Save index
    logger.info(f"Saving index to {output_dir}")
    indexer.save(str(output_dir))

    logger.info("✓ FAISS index built successfully")
    return indexer


def main():
    print("=" * 80)
    print("BUILDING PRODUCTION INDICES (SAFE MODE)")
    print("=" * 80)
    print()

    # Configuration
    ingestion_dir = Path("artifacts/ingestion_production")
    chunks_dir = ingestion_dir / "chunks"

    bm25_output = Path("artifacts/index_production/bm25")
    faiss_output = Path("artifacts/index_production/faiss")

    # Verify chunks directory exists
    if not chunks_dir.exists():
        print(f"❌ ERROR: Chunks directory not found: {chunks_dir}")
        return 1

    print(f"📂 Source: {chunks_dir}")
    print(f"📂 BM25 output: {bm25_output}")
    print(f"📂 FAISS output: {faiss_output}")
    print()

    # Load chunks
    logger.info("Step 1/4: Loading chunks...")
    chunks = load_chunks_from_dir(chunks_dir)

    if not chunks:
        print("❌ ERROR: No chunks loaded")
        return 1

    print(f"✓ Loaded {len(chunks):,} chunks")
    print()

    # Validate chunks
    logger.info("Step 2/4: Validating chunks...")
    if not validate_chunks(chunks):
        print("❌ ERROR: Chunk validation failed")
        return 1

    print("✓ Validation passed")
    print()

    # Build BM25 index
    logger.info("Step 3/4: Building BM25 index...")
    try:
        build_bm25_index(chunks, bm25_output)
        print("✓ BM25 index built")
        print()
    except Exception as e:
        logger.exception("BM25 index building failed")
        print(f"❌ ERROR: {e}")
        return 1

    # Build FAISS index
    logger.info("Step 4/4: Building FAISS index...")
    try:
        logger.info("Initializing embedding service...")
        embedding_service = get_embedding_service()

        build_faiss_index(chunks, faiss_output, embedding_service)
        print("✓ FAISS index built")
        print()
    except Exception as e:
        logger.exception("FAISS index building failed")
        print(f"❌ ERROR: {e}")
        return 1

    # Success!
    print("=" * 80)
    print("✅ ALL INDICES BUILT SUCCESSFULLY")
    print("=" * 80)
    print()
    print("📊 Index locations:")
    print(f"  • BM25: {bm25_output.absolute()}")
    print(f"  • FAISS: {faiss_output.absolute()}")
    print()
    print("🚀 Your system is ready! The 'page out of range' error should be fixed.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
