#!/usr/bin/env python
"""
Test ingestion pipeline performance with different worker counts
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger


def test_performance(source_dir: Path, workers_list: list = [1, 2, 4]):
    """Test ingestion performance with different worker counts"""

    results = []

    for workers in workers_list:
        output_dir = Path(f"artifacts/perf_test/workers_{workers}")

        logger.info(f"\n{'='*60}")
        logger.info(f"Testing with {workers} workers")
        logger.info(f"{'='*60}")

        # Clean output dir if exists
        if output_dir.exists():
            import shutil

            shutil.rmtree(output_dir)

        # Run ingestion
        cmd = [
            "python",
            "tools/ingest.py",
            "--source-dir",
            str(source_dir),
            "--output-dir",
            str(output_dir),
            "--workers",
            str(workers),
            "--chunk-size",
            "500",
        ]

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8"
            )

            duration = time.time() - start_time

            # Parse output for stats
            stats = {
                "workers": workers,
                "duration": duration,
                "success": result.returncode == 0,
                "output": result.stdout[-500:]
                if result.stdout
                else "",  # Last 500 chars
            }

            # Extract metrics from output
            for line in result.stdout.split("\n"):
                if "Total PDFs:" in line:
                    stats["total_pdfs"] = int(line.split(":")[1].strip())
                elif (
                    "Processed:" in line and "Processed:" == line.split(":")[0].strip()
                ):
                    stats["processed"] = int(line.split(":")[1].strip())
                elif "Failed:" in line:
                    stats["failed"] = int(line.split(":")[1].strip())
                elif "Total chunks:" in line:
                    stats["total_chunks"] = int(line.split(":")[1].strip())
                elif "Throughput:" in line:
                    throughput_str = line.split(":")[1].strip()
                    stats["throughput"] = float(throughput_str.split()[0])

            results.append(stats)

            logger.info(f"Workers: {workers}")
            logger.info(f"Duration: {duration:.2f}s")
            logger.info(f"Throughput: {stats.get('throughput', 'N/A')} PDFs/second")

        except Exception as e:
            logger.error(f"Error with {workers} workers: {e}")
            results.append(
                {
                    "workers": workers,
                    "duration": time.time() - start_time,
                    "success": False,
                    "error": str(e),
                }
            )

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test ingestion performance")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("data/raw/phase1_pilot"),
        help="Source directory with PDFs",
    )

    args = parser.parse_args()

    if not args.source_dir.exists():
        logger.error(f"Source directory not found: {args.source_dir}")
        sys.exit(1)

    # Test with different worker counts
    workers_to_test = [1, 2, 4]

    logger.info("=" * 60)
    logger.info("INGESTION PERFORMANCE TEST")
    logger.info(f"Source: {args.source_dir}")
    logger.info(f"Testing workers: {workers_to_test}")
    logger.info("=" * 60)

    results = test_performance(args.source_dir, workers_to_test)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("PERFORMANCE SUMMARY")
    logger.info("=" * 60)

    print(f"\n{'Workers':<10} {'Duration':<12} {'Throughput':<15} {'Speedup':<10}")
    print("-" * 50)

    baseline_duration = results[0]["duration"] if results else 1

    for result in results:
        if result["success"]:
            speedup = baseline_duration / result["duration"]
            print(
                f"{result['workers']:<10} {result['duration']:<12.2f} "
                f"{result.get('throughput', 0):<15.2f} {speedup:<10.2f}x"
            )
        else:
            print(f"{result['workers']:<10} {'FAILED':<12} {'-':<15} {'-':<10}")

    # Save results
    output_file = Path("artifacts/perf_test/performance_results.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
