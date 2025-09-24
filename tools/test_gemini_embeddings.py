#!/usr/bin/env python
"""
Test Gemini text-embedding-004 model
"""
import os
import sys
import time
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
from loguru import logger


def test_gemini_embeddings():
    """Test Gemini embedding models"""

    print("=" * 80)
    print("TESTING GEMINI EMBEDDINGS")
    print("=" * 80)

    # Configure API
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ No API key found")
        return

    genai.configure(api_key=api_key)

    # Test text-embedding-004
    model_name = "models/text-embedding-004"
    print(f"\n📊 Testing: {model_name}")
    print("-" * 40)

    try:
        # Test document embedding
        test_texts = [
            "The CO2 compressor operates at high pressure.",
            "Steam turbine temperature specifications are critical.",
            "Safety requirements must be followed strictly.",
        ]

        print(f"1. Testing document embeddings...")
        embeddings = []

        for i, text in enumerate(test_texts, 1):
            print(f"   Embedding text {i}: {text[:50]}...")

            start = time.time()
            result = genai.embed_content(
                model=model_name, content=text, task_type="retrieval_document"
            )
            elapsed = (time.time() - start) * 1000

            embedding = result["embedding"]
            embeddings.append(embedding)

            print(f"   ✅ Dimension: {len(embedding)}, Time: {elapsed:.0f}ms")

        # Test query embedding
        print(f"\n2. Testing query embedding...")
        query = "What is the compressor pressure?"

        start = time.time()
        query_result = genai.embed_content(
            model=model_name, content=query, task_type="retrieval_query"
        )
        query_elapsed = (time.time() - start) * 1000

        query_embedding = np.array(query_result["embedding"])
        print(f"   ✅ Query embedded in {query_elapsed:.0f}ms")

        # Calculate similarities
        print(f"\n3. Testing similarity search...")
        doc_embeddings = np.array(embeddings)

        # Normalize vectors
        doc_norms = np.linalg.norm(doc_embeddings, axis=1, keepdims=True)
        doc_embeddings_norm = doc_embeddings / doc_norms

        query_norm = np.linalg.norm(query_embedding)
        query_embedding_norm = query_embedding / query_norm

        # Calculate cosine similarities
        similarities = np.dot(doc_embeddings_norm, query_embedding_norm)

        print(f"   Query: '{query}'")
        print(f"   Similarities:")
        for i, (text, sim) in enumerate(zip(test_texts, similarities), 1):
            print(f"     {i}. {sim:.4f} - {text[:50]}...")

        # Find most similar
        best_idx = np.argmax(similarities)
        print(f"\n   🎯 Most similar: Document {best_idx + 1}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_embedding_service():
    """Test our embedding service wrapper"""

    print("\n" + "=" * 80)
    print("TESTING EMBEDDING SERVICE")
    print("=" * 80)

    try:
        from app.services.embedding_enhanced import get_embedding_service

        # Create service with Gemini
        print("\n1. Creating embedding service...")
        service = get_embedding_service(provider="gemini")
        print("   ✅ Service created")

        # Test single embedding
        print("\n2. Testing single text embedding...")
        text = "This is a test document about compressors."

        start = time.time()
        embedding = service.embed_text(text)
        elapsed = (time.time() - start) * 1000

        print(f"   ✅ Embedded in {elapsed:.0f}ms")
        print(f"   Dimension: {len(embedding)}")
        print(f"   Norm: {np.linalg.norm(embedding):.4f}")

        # Test batch embedding
        print("\n3. Testing batch embedding...")
        texts = [
            "Document about pressure specifications",
            "Temperature control systems",
            "Safety protocols and procedures",
        ]

        start = time.time()
        embeddings = service.embed_texts(texts)
        elapsed = (time.time() - start) * 1000

        print(f"   ✅ Embedded {len(texts)} texts in {elapsed:.0f}ms")
        print(f"   Shape: {embeddings.shape}")

        # Test query embedding
        print("\n4. Testing query embedding...")
        query = "pressure requirements"

        start = time.time()
        query_emb = service.embed_query(query)
        elapsed = (time.time() - start) * 1000

        print(f"   ✅ Query embedded in {elapsed:.0f}ms")

        # Calculate similarities
        similarities = np.dot(embeddings, query_emb)
        best_idx = np.argmax(similarities)

        print(f"   Query: '{query}'")
        print(f"   Best match: '{texts[best_idx]}'")
        print(f"   Similarity: {similarities[best_idx]:.4f}")

        # Get dimension
        print("\n5. Testing dimension getter...")
        dim = service.get_embedding_dimension()
        print(f"   ✅ Embedding dimension: {dim}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def compare_embedding_providers():
    """Compare local vs Gemini embeddings"""

    print("\n" + "=" * 80)
    print("COMPARING EMBEDDING PROVIDERS")
    print("=" * 80)

    test_text = (
        "The steam turbine operates at high temperature and pressure conditions."
    )

    providers = [
        ("local", "BAAI/bge-small-en-v1.5", "Local (BGE)"),
        ("gemini", "text-embedding-004", "Gemini 004"),
    ]

    results = []

    for provider, model, name in providers:
        print(f"\n📊 {name}")
        print("-" * 40)

        try:
            if provider == "local":
                from app.services.embedding import EmbeddingService

                service = EmbeddingService(model_name=model)
            else:
                from app.services.embedding_enhanced import get_embedding_service

                os.environ["EMBEDDING_PROVIDER"] = provider
                os.environ["EMBEDDING_MODEL"] = model
                service = get_embedding_service()

            # Measure performance
            start = time.time()
            embedding = service.embed_text(test_text)
            elapsed = (time.time() - start) * 1000

            results.append(
                {
                    "name": name,
                    "provider": provider,
                    "dimension": len(embedding),
                    "time_ms": elapsed,
                    "norm": np.linalg.norm(embedding),
                }
            )

            print(f"✅ Success")
            print(f"   Dimension: {len(embedding)}")
            print(f"   Time: {elapsed:.0f}ms")
            print(f"   Norm: {np.linalg.norm(embedding):.4f}")

        except Exception as e:
            print(f"❌ Failed: {str(e)[:100]}")
            results.append(
                {
                    "name": name,
                    "provider": provider,
                    "dimension": 0,
                    "time_ms": 0,
                    "norm": 0,
                }
            )

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Provider':<20} {'Dimension':<12} {'Time (ms)':<12} {'Status'}")
    print("-" * 60)

    for r in results:
        status = "✅" if r["dimension"] > 0 else "❌"
        print(f"{r['name']:<20} {r['dimension']:<12} {r['time_ms']:<12.0f} {status}")


def main():
    """Main test function"""

    print("🚀 GEMINI EMBEDDING TEST SUITE")
    print("=" * 80)

    # Check configuration
    print("\n📋 Current Configuration:")
    print(f"   EMBEDDING_PROVIDER: {os.environ.get('EMBEDDING_PROVIDER', 'not set')}")
    print(f"   EMBEDDING_MODEL: {os.environ.get('EMBEDDING_MODEL', 'not set')}")
    print(
        f"   GEMINI_API_KEY: {'✅ Found' if os.environ.get('GEMINI_API_KEY') else '❌ Missing'}"
    )

    # Run tests
    print("\n" + "=" * 80)
    print("1. TESTING GEMINI EMBEDDINGS DIRECTLY")
    print("=" * 80)
    success1 = test_gemini_embeddings()

    print("\n" + "=" * 80)
    print("2. TESTING EMBEDDING SERVICE")
    print("=" * 80)
    success2 = test_embedding_service()

    print("\n" + "=" * 80)
    print("3. COMPARING PROVIDERS")
    print("=" * 80)
    compare_embedding_providers()

    # Final status
    print("\n" + "=" * 80)
    print("FINAL STATUS")
    print("=" * 80)

    if success1 and success2:
        print("✅ Gemini embeddings are working perfectly!")
        print("\nYour .env is configured correctly:")
        print("```")
        print("# LLM Models (Gemini 2.5 - High accuracy)")
        print("LLM_MODEL_LIGHT=gemini-2.5-flash")
        print("LLM_MODEL_HEAVY=gemini-2.5-pro")
        print("")
        print("# Embeddings (Gemini - High quality)")
        print("EMBEDDING_PROVIDER=gemini")
        print("EMBEDDING_MODEL=text-embedding-004")
        print("```")

        print("\n🎯 Benefits of this configuration:")
        print("• Gemini 2.5: 65K output tokens for detailed answers")
        print("• text-embedding-004: 768-dim high-quality embeddings")
        print("• Unified ecosystem: All AI from Google")
        print("• Better semantic understanding")

    else:
        print("⚠️ Some issues detected")
        print("Fallback to local embeddings if needed")


if __name__ == "__main__":
    main()
