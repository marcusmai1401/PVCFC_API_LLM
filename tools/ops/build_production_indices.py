"""
Build BM25 and FAISS indices from production ingestion artifacts
"""
import json
import sys
from pathlib import Path

import numpy as np
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.rag.indexers.bm25_indexer import BM25Indexer
from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding_enhanced import get_embedding_service


def load_chunks(chunks_dir: Path):
    """Load all chunks from JSON files"""
    logger.info(f"Loading chunks from {chunks_dir}")

    all_chunks = []
    chunk_files = list(chunks_dir.glob("*_chunks.json"))

    if not chunk_files:
        logger.error(f"No chunk files found in {chunks_dir}")
        return []

    logger.info(f"Found {len(chunk_files)} chunk files")

    for chunk_file in chunk_files:
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
                all_chunks.extend(chunks)
        except Exception as e:
            logger.error(f"Failed to load {chunk_file}: {e}")

    logger.info(f"Loaded {len(all_chunks)} total chunks")
    return all_chunks


def build_bm25_index(chunks, output_dir: Path):
    """Build BM25 index"""
    logger.info("=" * 80)
    logger.info("Building BM25 Index")
    logger.info("=" * 80)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize indexer
    indexer = BM25Indexer()

    # Build index - pass chunks directly
    logger.info(f"Indexing {len(chunks)} chunks...")
    indexer.build_index(chunks)

    # Save index
    logger.info(f"Saving index to {output_dir}")
    indexer.save_index(str(output_dir))

    logger.info("✅ BM25 index built successfully")
    return indexer


def build_faiss_index(chunks, output_dir: Path, embedding_service):
    """Build FAISS vector index"""
    logger.info("=" * 80)
    logger.info("Building FAISS Vector Index")
    logger.info("=" * 80)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract texts and metadata
    texts = [chunk["text"] for chunk in chunks]
    metadatas = [chunk.get("metadata", {}) for chunk in chunks]

    # Embed chunks in batches
    logger.info(f"Embedding {len(chunks)} chunks...")
    logger.info("⚠️  This may take 10-20 minutes depending on chunk count...")

    embeddings_list = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch_end = min(i + batch_size, len(texts))
        batch_texts = texts[i:batch_end]

        logger.info(
            f"Embedding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size} [{i+1}-{batch_end}/{len(texts)}]"
        )

        # Embed batch
        batch_embeddings = embedding_service.embed_texts(batch_texts)
        embeddings_list.append(batch_embeddings)

    # Concatenate all embeddings
    logger.info("Concatenating embeddings...")
    embeddings = np.vstack(embeddings_list)

    # Build FAISS index
    logger.info(
        f"Building FAISS index with {len(embeddings)} vectors (dim={embeddings.shape[1]})..."
    )
    indexer = VectorIndexer()
    indexer.build(embeddings, texts, metadatas)

    # Save index
    logger.info(f"Saving index to {output_dir}")
    indexer.save(str(output_dir))

    logger.info("✅ FAISS index built successfully")
    return indexer


def main():
    print("=" * 80)
    print("BUILDING PRODUCTION INDICES")
    print("=" * 80)
    print()

    # Configuration
    ingestion_dir = Path("artifacts/ingestion_production")
    chunks_dir = ingestion_dir / "chunks"

    bm25_output = Path("artifacts/index_production/bm25")
    faiss_output = Path("artifacts/index_production/faiss")

    # Verify chunks exist
    if not chunks_dir.exists():
        print(f"❌ ERROR: Chunks directory not found: {chunks_dir}")
        print("   Please run ingestion first: python run_production_ingest.py")
        return 1

    # Load chunks
    chunks = load_chunks(chunks_dir)
    if not chunks:
        print("❌ ERROR: No chunks loaded")
        return 1

    print(f"📦 Loaded {len(chunks)} chunks")
    print(f"📂 BM25 output: {bm25_output}")
    print(f"📂 FAISS output: {faiss_output}")
    print()

    # Confirm
    response = input("Continue building indices? [y/N]: ")
    if response.lower() != "y":
        print("Cancelled by user.")
        return 0

    print()

    try:
        # Build BM25 index
        build_bm25_index(chunks, bm25_output)
        print()

        # Initialize embedding service
        logger.info("Initializing embedding service...")
        embedding_service = get_embedding_service()
        print()

        # Build FAISS index
        build_faiss_index(chunks, faiss_output, embedding_service)
        print()

        print("=" * 80)
        print("✅ ALL INDICES BUILT SUCCESSFULLY")
        print("=" * 80)
        print()
        print("📊 Index locations:")
        print(f"  • BM25: {bm25_output}")
        print(f"  • FAISS: {faiss_output}")
        print()
        print("🚀 Your application is now ready to use!")
        print("   Start with: streamlit run streamlit_app/app.py")

        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ INDEX BUILDING FAILED")
        print("=" * 80)
        print(f"Error: {e}")
        logger.exception("Full traceback:")
        return 1


if __name__ == "__main__":
    sys.exit(main())
