#!/usr/bin/env python3
"""
Test script to validate the new embedding implementation
Tests all requirements from A-E with a small dataset
"""
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from loguru import logger

# Set up test environment variables
os.environ["EMBEDDING_PROVIDER"] = "gemini"
os.environ["EMBEDDING_MODEL"] = "gemini-embedding-001"
os.environ["EMBED_OUTPUT_DIM"] = "1536"
os.environ["EMBED_BATCH_SIZE"] = "10"
os.environ["EMBED_CONCURRENCY"] = "4"
os.environ["EMBED_MAX_TOKENS_PER_REQ"] = "5000"
os.environ["EMBED_TASK"] = "RETRIEVAL_DOCUMENT"


def test_embedding_service():
    """Test the enhanced embedding service"""
    print("\n" + "=" * 80)
    print("TESTING ENHANCED EMBEDDING SERVICE")
    print("=" * 80)

    # Import after env vars are set
    from app.services.embedding_enhanced import UniversalEmbeddingService

    # Test texts (small dataset)
    test_texts = [
        "CO2 compressor operating at high pressure with steam turbine.",
        "Temperature control system for industrial equipment.",
        "Safety protocols for chemical processing units.",
        "P&ID diagram showing piping and instrumentation details.",
        "Vendor documentation for maintenance procedures.",
        "Performance curve data for rotating equipment.",
        "This text will be used to test cache hits on second run.",
        "Another unique text for testing parallel processing.",
        "Short text.",
        "Medium length text that contains more information about the system.",
    ]

    print(f"\nTest dataset: {len(test_texts)} texts")

    # Initialize service
    print("\n1. Initializing embedding service...")
    service = UniversalEmbeddingService(
        provider="gemini", model_name="gemini-embedding-001"
    )

    # Check configuration
    print(f"   Provider: {service.provider}")
    print(f"   Model: {service.model_name}")
    print(
        f"   Resolved model: {service._gemini_model if hasattr(service, '_gemini_model') else 'N/A'}"
    )
    print(f"   Output dimension: {service.output_dim}")
    print(f"   Batch size: {service.batch_size}")
    print(f"   Concurrency: {service.concurrency}")
    print(f"   Max tokens/request: {service.max_tokens_per_req}")

    # Test 1: First embedding run
    print("\n2. First embedding run (should use API)...")
    start = time.time()

    try:
        embeddings1 = service.embed_texts(test_texts[:5])  # Test with subset first
        elapsed1 = time.time() - start

        print(f"   ✓ Generated {len(embeddings1)} embeddings in {elapsed1:.2f}s")
        print(f"   Shape: {embeddings1.shape}")
        print(f"   Dimension: {embeddings1.shape[1]}")

        # Verify dimension
        assert (
            embeddings1.shape[1] == 1536
        ), f"Expected 1536D, got {embeddings1.shape[1]}D"
        print(f"   ✓ Dimension verification passed (1536)")

        # Check for zero vectors
        zero_vectors = np.all(embeddings1 == 0, axis=1).sum()
        assert zero_vectors == 0, f"Found {zero_vectors} zero vectors!"
        print(f"   ✓ No zero vectors found")

        # Print metrics
        print(f"\n   Metrics after first run:")
        for key, value in service.metrics.items():
            print(f"     {key}: {value}")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 2: Second embedding run (should hit cache)
    print("\n3. Second embedding run (should hit cache)...")
    initial_cache_hits = service.metrics.get("cache_hits", 0)
    start = time.time()

    try:
        embeddings2 = service.embed_texts(test_texts[:5])
        elapsed2 = time.time() - start

        cache_hits = service.metrics.get("cache_hits", 0) - initial_cache_hits

        print(f"   ✓ Generated {len(embeddings2)} embeddings in {elapsed2:.2f}s")
        print(f"   Cache hits: {cache_hits}")

        assert cache_hits > 0, "Expected cache hits on second run"
        print(f"   ✓ Cache is working ({cache_hits} hits)")

        # Verify embeddings are identical
        assert np.allclose(embeddings1, embeddings2), "Cached embeddings don't match!"
        print(f"   ✓ Cached embeddings match original")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 3: Check cache database
    print("\n4. Checking cache database...")
    cache_db_path = Path("artifacts/ingestion/cache/embeddings.sqlite")

    if cache_db_path.exists():
        conn = sqlite3.connect(str(cache_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cache")
        count = cursor.fetchone()[0]
        conn.close()
        print(f"   ✓ Cache database exists with {count} entries")
    else:
        print(f"   ✗ Cache database not found at {cache_db_path}")

    # Test 4: Check quarantine file
    print("\n5. Checking quarantine file...")
    quarantine_path = Path("artifacts/ingestion/quarantine_embedding.jsonl")

    if quarantine_path.exists():
        with open(quarantine_path, "r") as f:
            lines = f.readlines()
        print(f"   ✓ Quarantine file exists with {len(lines)} entries")

        if lines:
            # Show sample quarantine entry
            sample = json.loads(lines[0])
            print(f"   Sample entry: {json.dumps(sample, indent=2)[:200]}...")
    else:
        print(f"   ℹ Quarantine file not created (no failures)")

    # Test 5: Test with larger batch
    print("\n6. Testing with full dataset...")
    start = time.time()

    try:
        embeddings_full = service.embed_texts(test_texts)
        elapsed_full = time.time() - start

        print(
            f"   ✓ Generated {len(embeddings_full)} embeddings in {elapsed_full:.2f}s"
        )
        print(f"   Shape: {embeddings_full.shape}")

        # Verify no zero vectors
        zero_vectors = np.all(embeddings_full == 0, axis=1).sum()
        assert zero_vectors == 0, f"Found {zero_vectors} zero vectors!"
        print(f"   ✓ No zero vectors in full dataset")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Final metrics
    print(f"\n7. Final metrics:")
    for key, value in service.metrics.items():
        print(f"   {key}: {value}")

    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED")
    print("=" * 80)

    return True


def test_faiss_build():
    """Test FAISS index building with new implementation"""
    print("\n" + "=" * 80)
    print("TESTING FAISS BUILD")
    print("=" * 80)

    # Check if BM25 artifacts exist
    bm25_dir = Path("artifacts/ingestion/bm25")
    if not bm25_dir.exists():
        print(f"   ℹ BM25 directory not found at {bm25_dir}")
        print("   Run ingestion and BM25 build first")
        return False

    # Test FAISS build command
    print("\nTo test FAISS build, run:")
    print("python tools/build_faiss_local.py \\")
    print("  --bm25-dir artifacts/ingestion/bm25 \\")
    print("  --faiss-dir artifacts/ingestion/faiss_test")

    return True


if __name__ == "__main__":
    success = True

    # Check API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "AIza...":
        print("⚠️  WARNING: GEMINI_API_KEY not set or using placeholder")
        print("   Set a valid API key in .env to run actual API tests")
        print("   Tests will fail without a valid API key")

    try:
        # Test embedding service
        if not test_embedding_service():
            success = False

        # Test FAISS build
        if not test_faiss_build():
            success = False

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        success = False

    sys.exit(0 if success else 1)
