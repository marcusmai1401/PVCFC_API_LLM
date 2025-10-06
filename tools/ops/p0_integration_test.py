"""
P0: Complete Integration Test

End-to-end test covering:
1. GPU initialization with DLL path configuration
2. OCR GPU inference with fallback
3. Gemini embedding batch processing
4. Comprehensive logging and error handling

Usage:
    python tools/ops/p0_integration_test.py [--skip-ocr] [--skip-embedding] [--no-gpu]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import test modules
try:
    from app.core.gpu_utils import initialize_gpu_environment
    from tools.ops.p0_test_embedding_batch_sanity import (
        run_sanity_test as run_embedding_test,
    )
    from tools.ops.p0_test_ocr_gpu_sanity import run_sanity_test as run_ocr_test
except ImportError as e:
    logger.error(f"Failed to import test modules: {e}")
    logger.error("Make sure you're running from project root")
    sys.exit(1)


def print_header(title: str):
    """Print a formatted section header"""
    logger.info("\n")
    logger.info("=" * 80)
    logger.info(f"  {title}")
    logger.info("=" * 80)


def run_integration_test(
    skip_ocr: bool = False, skip_embedding: bool = False, prefer_gpu: bool = True
) -> dict:
    """
    Run complete P0 integration test

    Args:
        skip_ocr: Skip OCR test
        skip_embedding: Skip embedding test
        prefer_gpu: Prefer GPU over CPU

    Returns:
        Dictionary with test results
    """
    results = {
        "gpu_init": {"status": "not_run"},
        "ocr_test": {"status": "skipped" if skip_ocr else "not_run"},
        "embedding_test": {"status": "skipped" if skip_embedding else "not_run"},
        "overall_pass": False,
    }

    print_header("P0: COMPLETE INTEGRATION TEST")
    logger.info(f"Configuration:")
    logger.info(f"  Prefer GPU: {prefer_gpu}")
    logger.info(f"  Skip OCR: {skip_ocr}")
    logger.info(f"  Skip Embedding: {skip_embedding}")

    # Test 1: GPU Initialization
    print_header("TEST 1: GPU INITIALIZATION")

    try:
        gpu_info = initialize_gpu_environment(
            prefer_gpu=prefer_gpu, device_id=0, verbose=True
        )

        results["gpu_init"] = {
            "status": "pass",
            "cuda_available": gpu_info.cuda_available,
            "device": gpu_info.device_name,
            "cuda_version": gpu_info.cuda_version,
            "cudnn_version": gpu_info.cudnn_version,
            "dll_paths_count": len(gpu_info.dll_paths_added),
            "error": gpu_info.initialization_error,
        }

        logger.info("\n✓ GPU initialization test PASSED")

    except Exception as e:
        logger.error(f"\n✗ GPU initialization test FAILED: {e}")
        logger.exception(e)
        results["gpu_init"] = {
            "status": "fail",
            "error": str(e),
        }
        # Don't stop - continue with other tests

    # Test 2: OCR GPU Inference
    if not skip_ocr:
        print_header("TEST 2: OCR GPU INFERENCE")

        try:
            ocr_pass = run_ocr_test(prefer_gpu=prefer_gpu, device_id=0)

            results["ocr_test"] = {
                "status": "pass" if ocr_pass else "fail",
            }

            if ocr_pass:
                logger.info("\n✓ OCR GPU inference test PASSED")
            else:
                logger.error("\n✗ OCR GPU inference test FAILED")

        except Exception as e:
            logger.error(f"\n✗ OCR GPU inference test FAILED with exception: {e}")
            logger.exception(e)
            results["ocr_test"] = {
                "status": "fail",
                "error": str(e),
            }

    # Test 3: Embedding Batch Processing
    if not skip_embedding:
        print_header("TEST 3: GEMINI EMBEDDING BATCH")

        try:
            embedding_pass = run_embedding_test(
                num_texts=100, batch_size=256, expected_dim=768
            )

            results["embedding_test"] = {
                "status": "pass" if embedding_pass else "fail",
            }

            if embedding_pass:
                logger.info("\n✓ Embedding batch test PASSED")
            else:
                logger.error("\n✗ Embedding batch test FAILED")

        except Exception as e:
            logger.error(f"\n✗ Embedding batch test FAILED with exception: {e}")
            logger.exception(e)
            results["embedding_test"] = {
                "status": "fail",
                "error": str(e),
            }

    # Overall assessment
    results["overall_pass"] = all(
        result["status"] in ["pass", "skipped"]
        for result in [
            results["gpu_init"],
            results["ocr_test"],
            results["embedding_test"],
        ]
    )

    return results


def print_final_summary(results: dict):
    """Print final test summary"""
    print_header("FINAL SUMMARY")

    # GPU Init
    gpu_status = results["gpu_init"]["status"]
    if gpu_status == "pass":
        logger.info("✓ GPU Initialization: PASS")
        if results["gpu_init"].get("cuda_available"):
            logger.info(f"  Device: {results['gpu_init'].get('device')}")
            if results["gpu_init"].get("cuda_version"):
                logger.info(f"  CUDA: {results['gpu_init'].get('cuda_version')}")
            if results["gpu_init"].get("cudnn_version"):
                logger.info(f"  cuDNN: {results['gpu_init'].get('cudnn_version')}")
        else:
            logger.warning(f"  Fallback: CPU mode")
            if results["gpu_init"].get("error"):
                logger.warning(f"  Reason: {results['gpu_init'].get('error')}")
    else:
        logger.error(f"✗ GPU Initialization: {gpu_status.upper()}")

    # OCR Test
    ocr_status = results["ocr_test"]["status"]
    if ocr_status == "pass":
        logger.info("✓ OCR GPU Inference: PASS")
    elif ocr_status == "skipped":
        logger.info("⊘ OCR GPU Inference: SKIPPED")
    else:
        logger.error(f"✗ OCR GPU Inference: {ocr_status.upper()}")

    # Embedding Test
    embed_status = results["embedding_test"]["status"]
    if embed_status == "pass":
        logger.info("✓ Gemini Embedding Batch: PASS")
    elif embed_status == "skipped":
        logger.info("⊘ Gemini Embedding Batch: SKIPPED")
    else:
        logger.error(f"✗ Gemini Embedding Batch: {embed_status.upper()}")

    # Overall
    logger.info("\n" + "-" * 80)
    if results["overall_pass"]:
        logger.info("✓✓✓ OVERALL: ALL TESTS PASSED ✓✓✓")
        logger.info("\nP0 (GPU/cuDNN sanity & fallback) is COMPLETE and VALIDATED")
        logger.info("System is ready for:")
        logger.info("  - GPU-accelerated OCR processing")
        logger.info("  - Gemini API embedding batch processing")
        logger.info("  - Automatic CPU fallback on GPU errors")
    else:
        logger.error("✗✗✗ OVERALL: SOME TESTS FAILED ✗✗✗")
        logger.error("\nPlease review failed tests above")

    logger.info("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="P0: Complete Integration Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR test")

    parser.add_argument(
        "--skip-embedding", action="store_true", help="Skip embedding test"
    )

    parser.add_argument(
        "--no-gpu", action="store_true", help="Force CPU mode (disable GPU)"
    )

    args = parser.parse_args()

    prefer_gpu = not args.no_gpu

    # Run integration test
    results = run_integration_test(
        skip_ocr=args.skip_ocr,
        skip_embedding=args.skip_embedding,
        prefer_gpu=prefer_gpu,
    )

    # Print final summary
    print_final_summary(results)

    # Exit with appropriate code
    sys.exit(0 if results["overall_pass"] else 1)


if __name__ == "__main__":
    main()
