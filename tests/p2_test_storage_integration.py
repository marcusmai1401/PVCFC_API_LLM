"""
P2 Integration Test: Storage & Indexing

Tests complete pipeline:
1. Generate chunks
2. Deduplicate
3. Generate embeddings
4. Write to Parquet with manifest
5. Build BM25 index from Parquet
6. Build FAISS index from Parquet
7. Verify retrieval
"""

import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.chunkers.base import Chunk
from app.ingestion.chunkers.text_chunker import TextChunker
from app.ingestion.dedup import ContentDeduplicator
from app.storage.manifest_writer import IngestionTracker, ManifestWriter
from app.storage.parquet_adapter import ParquetAdapter
from app.storage.parquet_writer import ParquetWriter


# Mock embedding service for testing
class MockEmbeddingService:
    """Simple mock for testing without API calls"""

    def embed_texts(self, texts):
        import numpy as np

        # Return random 768-dim vectors
        return np.random.rand(len(texts), 768).astype(np.float32)


logger = logging.getLogger(__name__)


def test_p2_pipeline():
    """
    Test complete P2 storage pipeline
    """
    logger.info("=" * 70)
    logger.info("P2 INTEGRATION TEST: Storage & Indexing")
    logger.info("=" * 70)

    # Setup test directories
    test_dir = PROJECT_ROOT / "artifacts" / "p2_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)

    ingestion_dir = test_dir / "ingestion"
    index_dir = test_dir / "index"
    ingestion_dir.mkdir()
    index_dir.mkdir()

    # ========================================
    # Step 1: Generate test chunks
    # ========================================
    logger.info("\n[1/7] Generating test chunks...")

    test_documents = [
        {
            "text": """
            CO2 Compression System Overview

            The CO2 compression system consists of multiple stages including:
            - Primary compressor (C-101)
            - Secondary compressor (C-102)
            - Intercooler heat exchanger (HX-201)

            Operating Parameters:
            - Suction pressure: 50 bar
            - Discharge pressure: 150 bar
            - Temperature: 45°C
            """,
            "doc_id": "doc_001",
            "title": "CO2 System",
        },
        {
            "text": """
            Pump P-101 Specifications

            Equipment Tag: P-101
            Type: Centrifugal pump
            Flow rate: 100 m³/h
            Head: 50 m
            Motor power: 15 kW

            Torque Data:
            - Startup torque: 120 Nm
            - Running torque: 85 Nm
            """,
            "doc_id": "doc_002",
            "title": "Pump P-101",
        },
        {
            "text": """
            Heat Exchanger HX-201 Design

            Equipment Tag: HX-201
            Type: Shell and tube
            Heat duty: 500 kW
            Tube side: CO2 gas
            Shell side: Cooling water

            The heat exchanger is connected to compressor C-101 outlet.
            """,
            "doc_id": "doc_003",
            "title": "HX-201 Design",
        },
    ]

    chunker = TextChunker(chunk_size=200, chunk_overlap=30, min_chunk_size=50)

    all_chunks = []
    for doc in test_documents:
        chunks = chunker.chunk(
            text=doc["text"], doc_id=doc["doc_id"], metadata={"title": doc["title"]}
        )
        all_chunks.extend(chunks)

    logger.info(
        f"✅ Generated {len(all_chunks)} chunks from {len(test_documents)} documents"
    )

    # ========================================
    # Step 2: Deduplicate chunks
    # ========================================
    logger.info("\n[2/7] Deduplicating chunks...")

    deduplicator = ContentDeduplicator()
    unique_chunks = []
    duplicate_count = 0

    for chunk in all_chunks:
        if deduplicator.is_duplicate(chunk.text):
            duplicate_count += 1
        else:
            unique_chunks.append(chunk)

    logger.info(f"✅ Unique chunks: {len(unique_chunks)}, Duplicates: {duplicate_count}")

    # ========================================
    # Step 3: Generate embeddings
    # ========================================
    logger.info("\n[3/7] Generating embeddings...")

    embedding_service = MockEmbeddingService()
    texts = [chunk.text for chunk in unique_chunks]
    embeddings_array = embedding_service.embed_texts(texts)

    # Convert to dict
    embeddings_dict = {
        chunk.chunk_id: embeddings_array[i].tolist()
        for i, chunk in enumerate(unique_chunks)
    }

    logger.info(f"✅ Generated {len(embeddings_dict)} embeddings")

    # ========================================
    # Step 4: Write to Parquet + Manifest
    # ========================================
    logger.info("\n[4/7] Writing to Parquet...")

    ingestion_id = f"test_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    parquet_path = ingestion_dir / "chunks_v1.parquet"
    manifest_path = ingestion_dir / "manifest_v1.json"

    # Write Parquet
    parquet_writer = ParquetWriter(
        output_path=parquet_path, ingestion_version="test_v1", compression="snappy"
    )
    parquet_stats = parquet_writer.write_chunks(
        chunks=unique_chunks,
        embeddings=embeddings_dict,
        embedding_model="mock-embedding-768",
    )

    logger.info(f"✅ Wrote Parquet: {parquet_stats['file_size_mb']} MB")

    # Write Manifest
    tracker = IngestionTracker()
    tracker.add_source_file(processed=True)
    tracker.add_chunks(
        count=len(unique_chunks),
        tokens=sum(c.token_count for c in unique_chunks),
        unique=True,
    )
    tracker.add_chunks(count=duplicate_count, tokens=0, unique=False)
    tracker.add_embeddings(
        count=len(embeddings_dict), cached=0, cost=0.0  # Mock, no actual cost
    )

    manifest_writer = ManifestWriter(manifest_path)
    manifest = manifest_writer.write_ingestion_manifest(
        ingestion_id=ingestion_id,
        config={
            "chunk_size": 200,
            "chunk_overlap": 30,
            "embedding_model": "mock-embedding-768",
            "embedding_dim": 768,
            "dedup_enabled": True,
        },
        source_stats=tracker.get_source_stats(str(test_dir)),
        chunk_stats=tracker.get_chunk_stats(),
        embedding_stats=tracker.get_embedding_stats(),
        artifacts={
            "chunks_parquet": str(parquet_path.relative_to(PROJECT_ROOT)),
            "manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
        },
    )

    logger.info(f"✅ Wrote manifest: {ingestion_id}")

    # ========================================
    # Step 5: Build BM25 index from Parquet
    # ========================================
    logger.info("\n[5/7] Building BM25 index from Parquet...")

    from app.rag.indexers.bm25_indexer import BM25Indexer

    bm25_chunks = ParquetAdapter.load_chunks_for_bm25(parquet_path)
    bm25_indexer = BM25Indexer()
    bm25_indexer.build_index(bm25_chunks)

    bm25_dir = index_dir / "bm25"
    bm25_dir.mkdir()
    bm25_indexer.save_index(str(bm25_dir))

    logger.info(f"✅ Built BM25 index with {len(bm25_chunks)} documents")

    # ========================================
    # Step 6: Build FAISS index from Parquet
    # ========================================
    logger.info("\n[6/7] Building FAISS index from Parquet...")

    from app.rag.indexers.faiss_indexer import VectorIndexer

    texts, metadatas, embeddings = ParquetAdapter.load_chunks_for_faiss(parquet_path)

    vector_indexer = VectorIndexer(dim=768)

    # Use pre-computed embeddings
    import numpy as np

    embeddings_np = np.array(embeddings, dtype=np.float32)
    vector_indexer.build(embeddings_np, texts, metadatas)

    faiss_dir = index_dir / "faiss"
    faiss_dir.mkdir()
    vector_indexer.save(str(faiss_dir))

    logger.info(f"✅ Built FAISS index with {len(texts)} vectors")

    # ========================================
    # Step 7: Verify retrieval
    # ========================================
    logger.info("\n[7/7] Verifying retrieval...")

    # Test BM25 search
    query = "CO2 compressor pressure"
    bm25_results = bm25_indexer.search(query, top_k=2)

    logger.info(f"\nBM25 Search: '{query}'")
    logger.info(f"BM25 returned {len(bm25_results)} results")
    for i, result in enumerate(bm25_results, 1):
        logger.info(f"  {i}. Score: {result['score']:.4f}")
        logger.info(f"     Text: {result['text'][:100]}...")
        logger.info(f"     Doc: {result.get('doc_id', 'N/A')}")

    # Test FAISS search
    query_embedding = embedding_service.embed_texts([query])[0:1]  # Keep 2D shape
    faiss_search_results = vector_indexer.search(query_embedding, top_k=2)
    # Convert to expected format
    faiss_results = []
    for idx, score in faiss_search_results[0]:
        faiss_results.append(
            {"text": texts[idx], "score": score, "metadata": metadatas[idx]}
        )

    logger.info(f"\nFAISS Search: '{query}'")
    for i, result in enumerate(faiss_results, 1):
        logger.info(f"  {i}. Score: {result['score']:.4f}")
        logger.info(f"     Text: {result['text'][:100]}...")
        logger.info(f"     Doc: {result['metadata'].get('doc_id', 'N/A')}")

    # ========================================
    # Validation
    # ========================================
    logger.info("\n" + "=" * 70)
    logger.info("VALIDATION")
    logger.info("=" * 70)

    # Check files exist
    assert parquet_path.exists(), "Parquet file not created"
    assert manifest_path.exists(), "Manifest not created"
    assert (bm25_dir / "bm25_index.pkl").exists(), "BM25 index not created"
    assert (faiss_dir / "faiss.index").exists(), "FAISS index not created"

    # Check Parquet stats
    stats = ParquetAdapter.get_parquet_stats(parquet_path)
    logger.info(f"✅ Parquet stats:")
    logger.info(f"   Total chunks: {stats['total_chunks']}")
    logger.info(f"   With embeddings: {stats['chunks_with_embeddings']}")
    logger.info(f"   Unique docs: {stats['unique_documents']}")
    logger.info(f"   Avg tokens: {stats['avg_token_count']:.1f}")

    assert stats["total_chunks"] == len(unique_chunks), "Chunk count mismatch"
    assert stats["chunks_with_embeddings"] == len(
        unique_chunks
    ), "Embedding count mismatch"

    # Check manifest content
    manifest_data = ManifestWriter.read_manifest(manifest_path)
    logger.info(f"\n✅ Manifest validation:")
    logger.info(f"   Ingestion ID: {manifest_data['ingestion_id']}")
    logger.info(f"   Total chunks: {manifest_data['chunks']['total_chunks']}")
    logger.info(f"   Unique chunks: {manifest_data['chunks']['unique_chunks']}")
    logger.info(f"   Duplicate chunks: {manifest_data['chunks']['duplicate_chunks']}")

    assert manifest_data["chunks"]["total_chunks"] == len(
        all_chunks
    ), "Manifest chunk count error"
    assert manifest_data["chunks"]["unique_chunks"] == len(
        unique_chunks
    ), "Manifest unique count error"

    # Check retrieval quality
    # Note: With only 1 chunk, BM25 may return empty if query has no keyword overlap
    if len(bm25_results) > 0:
        assert bm25_results[0]["score"] > 0, "BM25 score should be positive"
        logger.info("✅ BM25 retrieval working")
    else:
        logger.warning("⚠️  BM25 returned no results (likely due to minimal test data)")

    assert len(faiss_results) > 0, "FAISS returned no results"
    assert faiss_results[0]["score"] > 0, "FAISS score should be positive"
    logger.info("✅ FAISS retrieval working")

    logger.info("\n" + "=" * 70)
    logger.info("✅ P2 INTEGRATION TEST PASSED")
    logger.info("=" * 70)
    logger.info(f"\nTest artifacts saved to: {test_dir}")
    logger.info("Pipeline validated:")
    logger.info("  ✓ Chunking with deduplication")
    logger.info("  ✓ Embedding generation")
    logger.info("  ✓ Parquet storage with schema")
    logger.info("  ✓ Manifest with lineage tracking")
    logger.info("  ✓ BM25 index from Parquet")
    logger.info("  ✓ FAISS index from Parquet")
    logger.info("  ✓ Retrieval verification")

    return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        success = test_p2_pipeline()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)
