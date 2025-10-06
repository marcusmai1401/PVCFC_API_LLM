"""
Re-index script with Phase 1 fixes applied
Rebuilds BM25 and FAISS indexes from existing chunks
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from app.rag.indexers.bm25_indexer import BM25Indexer
from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding_enhanced import EmbeddingService

# Paths
CHUNKS_JSONL = Path("artifacts/ingestion/chunks/chunks.jsonl")
BM25_INDEX_DIR = Path("artifacts/index/bm25")
FAISS_INDEX_DIR = Path("artifacts/index/faiss")


def load_chunks_with_page_fix(jsonl_path: Path):
    """
    Load chunks from JSONL and apply Phase 1 page extraction fix
    """
    from app.ingestion.text_chunker import extract_page_from_content

    logger.info(f"Loading chunks from: {jsonl_path}")
    chunks = []
    page_fixes_count = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk = json.loads(line)

                # PHASE 1 FIX: Extract page from content
                text = chunk.get("text", "")
                content_page = extract_page_from_content(text)

                if content_page is not None:
                    # Override metadata page with content page
                    old_page = chunk.get("metadata", {}).get("page", "N/A")
                    if "metadata" not in chunk:
                        chunk["metadata"] = {}
                    chunk["metadata"]["page"] = content_page

                    if old_page != content_page:
                        page_fixes_count += 1
                        if page_fixes_count <= 5:  # Log first 5 fixes
                            logger.debug(
                                f"Page fix: chunk {chunk.get('chunk_id', '?')[:50]}... "
                                f"old_page={old_page} -> new_page={content_page}"
                            )

                chunks.append(chunk)

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON at line {line_num}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error at line {line_num}: {e}")
                continue

    logger.info(f"Loaded {len(chunks)} chunks")
    logger.info(f"Applied page fixes to {page_fixes_count} chunks")

    return chunks


def build_bm25_index(chunks, output_dir: Path):
    """Build BM25 index"""
    logger.info("=" * 70)
    logger.info("BUILDING BM25 INDEX")
    logger.info("=" * 70)

    # Prepare chunk dicts for BM25Indexer.build_index()
    chunk_dicts = []

    for chunk in chunks:
        chunk_dict = {
            "text": chunk.get("text", ""),
            "chunk_id": chunk.get("chunk_id"),
            "doc_id": chunk.get("doc_id"),
            "page": chunk.get("metadata", {}).get("page", 1),
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "heading": chunk.get("heading"),
            "level": chunk.get("level", 0),
        }

        # Add any other metadata fields
        if "metadata" in chunk:
            for k, v in chunk["metadata"].items():
                if k not in chunk_dict:
                    chunk_dict[k] = v

        chunk_dicts.append(chunk_dict)

    logger.info(f"Indexing {len(chunk_dicts)} documents...")

    # Build index using correct API: build_index(chunks)
    indexer = BM25Indexer()
    indexer.build_index(chunk_dicts)

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    indexer.save_index(str(output_dir))

    logger.info(f"✓ BM25 index saved to {output_dir}")

    # Verify
    stats = indexer.get_statistics()
    logger.info(
        f"Index stats: {stats['num_documents']} docs, "
        f"avg length: {stats['avg_doc_length']:.1f} tokens"
    )

    return indexer


def build_faiss_index(chunks, output_dir: Path):
    """Build FAISS index"""
    logger.info("=" * 70)
    logger.info("BUILDING FAISS INDEX")
    logger.info("=" * 70)

    # Initialize embedding service
    embedding_service = EmbeddingService()

    # Prepare texts and metadata
    texts = []
    metadatas = []

    for chunk in chunks:
        texts.append(chunk.get("text", ""))

        metadata = {
            "chunk_id": chunk.get("chunk_id"),
            "doc_id": chunk.get("doc_id"),
            "page": chunk.get("metadata", {}).get("page", 1),
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "heading": chunk.get("heading"),
            "level": chunk.get("level", 0),
        }

        # Add extra metadata
        if "metadata" in chunk:
            for k, v in chunk["metadata"].items():
                if k not in metadata:
                    metadata[k] = v

        metadatas.append(metadata)

    logger.info(f"Embedding {len(texts)} documents...")
    logger.info("(This may take several minutes depending on text volume...)")

    # Generate embeddings
    embeddings = embedding_service.embed_texts(texts)
    logger.info(f"✓ Embeddings generated: shape={embeddings.shape}")

    # Build index using correct API: build(embeddings, texts, metadatas)
    indexer = VectorIndexer()
    indexer.build(embeddings, texts, metadatas)

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    indexer.save(str(output_dir))

    logger.info(f"✓ FAISS index saved to {output_dir}")
    logger.info(f"Dimension: {indexer.dim}, Docs: {len(indexer.documents)}")

    return indexer


def main():
    logger.info("=" * 70)
    logger.info("RE-INDEXING WITH PHASE 1 FIXES")
    logger.info("=" * 70)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")

    # Check chunks file
    if not CHUNKS_JSONL.exists():
        logger.error(f"Chunks file not found: {CHUNKS_JSONL}")
        logger.error("Please run ingestion first!")
        sys.exit(1)

    # Load chunks with page fix
    chunks = load_chunks_with_page_fix(CHUNKS_JSONL)

    if not chunks:
        logger.error("No chunks loaded!")
        sys.exit(1)

    # Build BM25 index
    try:
        bm25_indexer = build_bm25_index(chunks, BM25_INDEX_DIR)
        logger.info("✓ BM25 indexing successful")
    except Exception as e:
        logger.error(f"✗ BM25 indexing failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Build FAISS index
    try:
        faiss_indexer = build_faiss_index(chunks, FAISS_INDEX_DIR)
        logger.info("✓ FAISS indexing successful")
    except Exception as e:
        logger.error(f"✗ FAISS indexing failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Final summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("RE-INDEXING COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Total chunks processed: {len(chunks)}")
    logger.info(f"BM25 index: {BM25_INDEX_DIR}")
    logger.info(f"FAISS index: {FAISS_INDEX_DIR}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Verify metadata with: python analyze_chunks_final.py")
    logger.info("  2. Test query with torque question")
    logger.info("  3. Check citations point to correct pages")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
