"""
P0: Gemini Embedding Batch Sanity Test

Tests Gemini API embedding service with batch processing.
Measures p95 latency and verifies output dimensions.

Usage:
    python tools/ops/p0_test_embedding_batch_sanity.py [--num-texts 100] [--batch-size 256]
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from app.services.embedding_enhanced import UniversalEmbeddingService

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_test_texts(num_texts: int = 100) -> List[str]:
    """
    Generate test texts with varying lengths

    Args:
        num_texts: Number of texts to generate

    Returns:
        List of test texts
    """
    test_texts = []

    # Short texts (equipment tags)
    short_templates = [
        "P-101: Centrifugal pump for lube oil system",
        "HX-202: Heat exchanger for cooling water",
        "V-303: Control valve for pressure regulation",
        "E-404: Compressor for CO2 gas",
        "T-505: Storage tank for diesel fuel",
    ]

    # Medium texts (technical descriptions)
    medium_templates = [
        "The centrifugal pump operates at 3560 RPM with a maximum flow rate of 250 GPM. "
        "It is designed for continuous operation at temperatures up to 200°F.",
        "Heat exchanger specifications: shell-and-tube type, stainless steel construction, "
        "design pressure 150 PSI, operating temperature range -20°F to 300°F.",
        "Control valve actuated by pneumatic diaphragm, CV=45, designed for on-off and "
        "throttling service with tight shutoff requirements.",
    ]

    # Long texts (detailed specifications)
    long_templates = [
        "The CO2 compressor system consists of a two-stage centrifugal compressor with intercooling. "
        "First stage operates at 5,000 RPM delivering 1200 SCFM at 50 PSI discharge pressure. "
        "Second stage operates at 8,000 RPM delivering 1200 SCFM at 150 PSI discharge pressure. "
        "The system includes anti-surge control, vibration monitoring, and automatic shutdown on high temperature.",
        "Lube oil system specification: capacity 500 gallons, circulation rate 100 GPM, filtration "
        "5 micron absolute, operating temperature 120-140°F maintained by heat exchanger with "
        "automatic temperature control valve. System includes duplex filters with differential "
        "pressure indicators and low pressure alarm at 15 PSI.",
    ]

    # Vietnamese texts
    vietnamese_templates = [
        "Bơm ly tâm cho hệ thống dầu bôi trơn",
        "Thiết bị trao đổi nhiệt cho nước làm mát",
        "Van điều khiển để điều chỉnh áp suất",
        "Máy nén khí CO2 hai tầng với làm mát trung gian",
    ]

    # Generate mixed texts
    for i in range(num_texts):
        if i % 10 == 0:
            # Vietnamese text
            text = vietnamese_templates[i % len(vietnamese_templates)]
        elif i % 4 == 0:
            # Long text
            text = long_templates[i % len(long_templates)]
        elif i % 2 == 0:
            # Medium text
            text = medium_templates[i % len(medium_templates)]
        else:
            # Short text
            text = short_templates[i % len(short_templates)]

        test_texts.append(f"[{i+1}] {text}")

    return test_texts


def calculate_p95_latency(latencies: List[float]) -> float:
    """Calculate p95 latency from list of latencies"""
    if not latencies:
        return 0.0

    sorted_latencies = sorted(latencies)
    idx = int(len(sorted_latencies) * 0.95)
    return sorted_latencies[min(idx, len(sorted_latencies) - 1)]


def test_embedding_batch(
    num_texts: int = 100, batch_size: int = 256, expected_dim: int = 768
) -> Dict:
    """
    Run embedding batch test

    Args:
        num_texts: Number of texts to embed
        batch_size: Batch size for processing
        expected_dim: Expected embedding dimension

    Returns:
        Dictionary with test results
    """
    results = {
        "success": False,
        "num_texts": num_texts,
        "batch_size": batch_size,
        "total_time": None,
        "avg_latency_per_text": None,
        "p95_latency": None,
        "embeddings_shape": None,
        "expected_dim": expected_dim,
        "actual_dim": None,
        "dimension_match": False,
        "error": None,
        "provider": None,
        "model": None,
    }

    try:
        # Check API key
        api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or settings")

        logger.info(f"API Key present: {api_key[:10]}...{api_key[-4:]}")

        # Initialize embedding service
        logger.info(
            f"Initializing embedding service (provider={settings.embedding_provider}, model={settings.embedding_model})..."
        )

        embedding_service = UniversalEmbeddingService(
            provider=settings.embedding_provider or "gemini",
            model_name=settings.embedding_model or "gemini-embedding-001",
        )

        results["provider"] = embedding_service.provider
        results["model"] = embedding_service.model_name

        logger.info(f"✓ Embedding service initialized")
        logger.info(f"  Provider: {embedding_service.provider}")
        logger.info(f"  Model: {embedding_service.model_name}")
        logger.info(f"  Output dimension: {embedding_service.output_dim}")
        logger.info(f"  Batch size: {embedding_service.batch_size}")
        logger.info(f"  Concurrency: {embedding_service.concurrency}")

        # Generate test texts
        logger.info(f"\nGenerating {num_texts} test texts...")
        test_texts = generate_test_texts(num_texts)

        logger.info(f"✓ Generated {len(test_texts)} test texts")
        logger.info(f"  Sample texts:")
        for i in range(min(3, len(test_texts))):
            preview = (
                test_texts[i][:80] + "..." if len(test_texts[i]) > 80 else test_texts[i]
            )
            logger.info(f"    {i+1}. {preview}")

        # Run batch embedding
        logger.info(f"\nRunning batch embedding...")
        logger.info(f"  Number of texts: {num_texts}")
        logger.info(f"  Batch size: {batch_size}")

        t0 = time.time()

        embeddings = embedding_service.embed_texts(test_texts, batch_size=batch_size)

        total_time = time.time() - t0

        # Calculate metrics
        results["total_time"] = total_time
        results["avg_latency_per_text"] = total_time / num_texts
        results["embeddings_shape"] = embeddings.shape
        results["actual_dim"] = (
            embeddings.shape[1] if len(embeddings.shape) > 1 else None
        )
        results["dimension_match"] = results["actual_dim"] == expected_dim

        # For p95 latency, we approximate by total_time / num_batches
        num_batches = (num_texts + batch_size - 1) // batch_size
        batch_latency = total_time / num_batches
        results[
            "p95_latency"
        ] = batch_latency  # Simplified - actual p95 would need per-batch timing

        results["success"] = True

        logger.info(f"✓ Embedding batch completed successfully")
        logger.info(f"  Total time: {total_time:.2f}s")
        logger.info(
            f"  Avg latency per text: {results['avg_latency_per_text']*1000:.2f}ms"
        )
        logger.info(f"  Estimated p95 latency: {results['p95_latency']:.2f}s")
        logger.info(f"  Embeddings shape: {embeddings.shape}")
        logger.info(f"  Expected dimension: {expected_dim}")
        logger.info(f"  Actual dimension: {results['actual_dim']}")
        logger.info(f"  Dimension match: {'✓' if results['dimension_match'] else '✗'}")

        # Verify embeddings are not all zeros
        if np.allclose(embeddings, 0):
            logger.warning("⚠ Warning: Embeddings are all zeros!")
        else:
            mean_norm = np.mean(np.linalg.norm(embeddings, axis=1))
            logger.info(f"  Mean embedding norm: {mean_norm:.4f}")

    except Exception as e:
        error_msg = f"Embedding batch test failed: {str(e)}"
        logger.error(f"✗ {error_msg}")
        logger.exception(e)
        results["error"] = error_msg

    return results


def run_sanity_test(
    num_texts: int = 100, batch_size: int = 256, expected_dim: int = 768
) -> bool:
    """
    Run complete Gemini embedding batch sanity test

    Args:
        num_texts: Number of texts to embed
        batch_size: Batch size for processing
        expected_dim: Expected embedding dimension

    Returns:
        True if test passes, False otherwise
    """
    logger.info("=" * 70)
    logger.info("P0: GEMINI EMBEDDING BATCH SANITY TEST")
    logger.info("=" * 70)

    # Run test
    results = test_embedding_batch(
        num_texts=num_texts, batch_size=batch_size, expected_dim=expected_dim
    )

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Provider: {results['provider']}")
    logger.info(f"Model: {results['model']}")
    logger.info(f"Number of Texts: {results['num_texts']}")
    logger.info(f"Batch Size: {results['batch_size']}")

    logger.info(f"\nTest Result: {'✓ PASSED' if results['success'] else '✗ FAILED'}")

    if results["success"]:
        logger.info(f"  Total Time: {results['total_time']:.2f}s")
        logger.info(f"  Avg Latency/Text: {results['avg_latency_per_text']*1000:.2f}ms")
        logger.info(f"  Est. p95 Latency: {results['p95_latency']:.2f}s")
        logger.info(f"  Embeddings Shape: {results['embeddings_shape']}")
        logger.info(
            f"  Dimension Match: {'✓ YES' if results['dimension_match'] else '✗ NO'}"
        )

        # Performance assessment
        avg_latency_ms = results["avg_latency_per_text"] * 1000
        if avg_latency_ms < 50:
            logger.info(f"\n✓ Performance: EXCELLENT (< 50ms/text)")
        elif avg_latency_ms < 100:
            logger.info(f"\n✓ Performance: GOOD (< 100ms/text)")
        elif avg_latency_ms < 200:
            logger.info(f"\n⚠ Performance: ACCEPTABLE (< 200ms/text)")
        else:
            logger.info(f"\n⚠ Performance: SLOW (> 200ms/text)")
    else:
        logger.error(f"  Error: {results['error']}")

    logger.info("=" * 70)

    return results["success"] and results["dimension_match"]


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="P0: Gemini Embedding Batch Sanity Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--num-texts",
        type=int,
        default=100,
        help="Number of texts to embed (default: 100)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Batch size for processing (default: 256)",
    )

    parser.add_argument(
        "--expected-dim",
        type=int,
        default=768,
        help="Expected embedding dimension (default: 768)",
    )

    args = parser.parse_args()

    # Run test
    success = run_sanity_test(
        num_texts=args.num_texts,
        batch_size=args.batch_size,
        expected_dim=args.expected_dim,
    )

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
