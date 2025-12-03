#!/usr/bin/env python
"""
Performance Benchmark: TagNormalizer Instantiation Overhead
============================================================

Hypothesis: Re-instantiating TagNormalizer per chunk caused massive slowdown
Test: Singleton (outside loop) vs Per-chunk (inside loop) instantiation
Data: Production chunks from D:\PVCFC_Artifacts\ingestion_production\chunks\chunks.jsonl

Author: Auto-generated diagnostic script
Date: 2025-11-27
"""

import json
import sys
import time
from pathlib import Path
from typing import List

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration
CHUNKS_FILE = Path(r"D:\PVCFC_Artifacts\ingestion_production\chunks\chunks.jsonl")
OLD_DATASET_SIZE = 68000  # User's previous dataset size


def load_text_samples(max_samples: int = None) -> List[str]:
    """Load text samples from chunks.jsonl"""
    print(f"📂 Loading chunks from: {CHUNKS_FILE}")

    if not CHUNKS_FILE.exists():
        print(f"❌ ERROR: File not found: {CHUNKS_FILE}")
        sys.exit(1)

    texts = []
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                chunk = json.loads(line.strip())
                if "text" in chunk and chunk["text"]:
                    texts.append(chunk["text"])

                if max_samples and len(texts) >= max_samples:
                    break

            except json.JSONDecodeError as e:
                print(f"⚠️  Warning: Failed to parse line {i+1}: {e}")
                continue

    print(f"✅ Loaded {len(texts):,} text samples\n")
    return texts


def benchmark_optimized(texts: List[str]) -> float:
    """Test Case 1: Singleton TagNormalizer (OPTIMIZED - Current Code)"""
    from app.rag.normalizers.tag_normalizer import TagNormalizer

    print("=" * 80)
    print("TEST 1: OPTIMIZED (Singleton - Outside Loop)")
    print("=" * 80)

    # Instantiate ONCE before loop
    normalizer = TagNormalizer()
    print(f"✓ TagNormalizer instantiated ONCE (singleton pattern)")

    start_time = time.perf_counter()

    total_tags = 0
    for text in texts:
        tags = normalizer.extract_tags(text)
        total_tags += len(tags)

    end_time = time.perf_counter()
    elapsed = end_time - start_time

    print(f"✓ Processed {len(texts):,} chunks")
    print(f"✓ Extracted {total_tags:,} tags total")
    print(f"⏱️  Time: {elapsed:.4f} seconds")
    print(f"📊 Rate: {len(texts)/elapsed:.2f} chunks/sec\n")

    return elapsed


def benchmark_unoptimized(texts: List[str]) -> float:
    """Test Case 2: Per-chunk TagNormalizer (UNOPTIMIZED - The Bug)"""
    from app.rag.normalizers.tag_normalizer import TagNormalizer

    print("=" * 80)
    print("TEST 2: UNOPTIMIZED (Per-chunk - Inside Loop)")
    print("=" * 80)
    print("⚠️  Instantiating TagNormalizer INSIDE loop for EVERY chunk...")

    start_time = time.perf_counter()

    total_tags = 0
    for text in texts:
        # ❌ BUG: Instantiate INSIDE loop (wasteful!)
        normalizer = TagNormalizer()
        tags = normalizer.extract_tags(text)
        total_tags += len(tags)

    end_time = time.perf_counter()
    elapsed = end_time - start_time

    print(f"✓ Processed {len(texts):,} chunks")
    print(f"✓ Extracted {total_tags:,} tags total")
    print(f"⏱️  Time: {elapsed:.4f} seconds")
    print(f"📊 Rate: {len(texts)/elapsed:.2f} chunks/sec\n")

    return elapsed


def format_time(seconds: float) -> str:
    """Convert seconds to human-readable format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {secs:.1f}s"
    elif minutes > 0:
        return f"{minutes}m {secs:.1f}s"
    else:
        return f"{secs:.2f}s"


def print_analysis(time_optimized: float, time_slow: float, num_chunks: int):
    """Print detailed analysis and extrapolation"""
    print("\n" + "=" * 80)
    print("📊 PERFORMANCE ANALYSIS")
    print("=" * 80)

    # Basic metrics
    print(f"\n{'Metric':<40} {'Optimized':<20} {'Unoptimized':<20}")
    print("-" * 80)
    print(
        f"{'Total Time':<40} {format_time(time_optimized):<20} {format_time(time_slow):<20}"
    )
    print(f"{'Chunks Processed':<40} {num_chunks:,}")
    print(
        f"{'Processing Rate (chunks/sec)':<40} {num_chunks/time_optimized:.2f}{'':<16} {num_chunks/time_slow:.2f}"
    )

    # Speedup calculation
    speedup = time_slow / time_optimized
    print(f"\n🚀 SPEEDUP FACTOR: {speedup:.2f}x faster")
    print(f"   (Optimized is {speedup:.2f} times faster than unoptimized)")

    # Cost per instantiation
    overhead_total = time_slow - time_optimized
    cost_per_instantiation = overhead_total / num_chunks

    print(f"\n💰 COST PER INSTANTIATION:")
    print(f"   Total overhead: {format_time(overhead_total)}")
    print(f"   Per-chunk overhead: {cost_per_instantiation*1000:.4f} milliseconds")
    print(f"   ({cost_per_instantiation:.6f} seconds)")

    # The critical extrapolation
    print("\n" + "=" * 80)
    print("🔮 EXTRAPOLATION TO 68,000 CHUNKS (Old Dataset Size)")
    print("=" * 80)

    # Optimized extrapolation
    time_opt_68k = (num_chunks / time_optimized) and (
        OLD_DATASET_SIZE / (num_chunks / time_optimized)
    )
    time_opt_68k_final = (OLD_DATASET_SIZE * time_optimized) / num_chunks

    # Unoptimized extrapolation
    time_slow_68k = cost_per_instantiation * OLD_DATASET_SIZE + time_opt_68k_final

    print(f"\nWith OPTIMIZED approach (singleton):")
    print(f"   Estimated time: {format_time(time_opt_68k_final)}")

    print(f"\nWith UNOPTIMIZED approach (per-chunk instantiation):")
    print(f"   Base processing: {format_time(time_opt_68k_final)}")
    print(
        f"   Instantiation overhead: {format_time(cost_per_instantiation * OLD_DATASET_SIZE)}"
    )
    print(f"   TOTAL TIME: {format_time(time_slow_68k)}")

    # The verdict
    waste = time_slow_68k - time_opt_68k_final
    print(f"\n⚠️  TIME WASTED by re-instantiation:")
    print(f"   {format_time(waste)}")
    print(f"   ({waste/3600:.2f} hours!)")

    # Compare with user's 7-hour experience
    print(f"\n" + "=" * 80)
    print("🎯 VERDICT: Does this explain the 7-hour slowdown?")
    print("=" * 80)

    if waste >= 6 * 3600:  # 6+ hours
        print(f"✅ YES! Instantiation overhead could explain it!")
        print(f"   Estimated waste: {format_time(waste)}")
        print(f"   User experienced: ~7 hours slowdown")
        print(f"   Match: This is the likely culprit! 🎉")
    elif waste >= 3 * 3600:  # 3-6 hours
        print(f"⚠️  PARTIALLY. Significant overhead found:")
        print(f"   Estimated waste: {format_time(waste)}")
        print(f"   This is a major contributor, but may not be the only factor")
    else:
        print(f"❌ UNLIKELY. Overhead too small:")
        print(f"   Estimated waste: {format_time(waste)}")
        print(f"   Need to investigate other factors")

    print("\n" + "=" * 80)


def main():
    """Main benchmark execution"""
    print("\n" + "=" * 80)
    print("TagNormalizer Performance Benchmark")
    print("=" * 80)
    print(f"Hypothesis: Per-chunk instantiation caused 7-hour slowdown")
    print(f"Test Dataset: Production chunks from ingestion")
    print(f"Extrapolation Target: {OLD_DATASET_SIZE:,} chunks (old dataset)")
    print("=" * 80 + "\n")

    # Import check
    try:
        from app.rag.normalizers.tag_normalizer import TagNormalizer

        print("✅ TagNormalizer imported successfully\n")
    except ImportError as e:
        print(f"❌ ERROR: Cannot import TagNormalizer")
        print(f"   {e}")
        print(f"\nPlease ensure:")
        print(f"   1. Script is run from project root")
        print(f"   2. TagNormalizer exists at: app/rag/normalizers/tag_normalizer.py")
        sys.exit(1)

    # Load data
    text_samples = load_text_samples()

    if len(text_samples) == 0:
        print("❌ ERROR: No text samples loaded")
        sys.exit(1)

    num_chunks = len(text_samples)

    # Run benchmarks
    print("🏁 Starting benchmarks...\n")

    # Test 1: Optimized
    time_optimized = benchmark_optimized(text_samples)

    # Small delay
    time.sleep(1)

    # Test 2: Unoptimized
    time_slow = benchmark_unoptimized(text_samples)

    # Analysis
    print_analysis(time_optimized, time_slow, num_chunks)

    print("\n✅ Benchmark complete!\n")


if __name__ == "__main__":
    main()
