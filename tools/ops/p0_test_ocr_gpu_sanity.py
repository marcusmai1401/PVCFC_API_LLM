"""
P0: OCR GPU Sanity Test

Tests PaddleOCR GPU inference with proper GPU initialization and fallback.
Measures inference time and validates GPU is being used correctly.

Usage:
    python tools/ops/p0_test_ocr_gpu_sanity.py [--prefer-gpu] [--device-id 0]
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.gpu_utils import GPUInfo, initialize_gpu_environment

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def find_test_pdf(data_dir: str = r"D:\Data_Raw") -> Optional[Path]:
    """Find a test PDF file from data directory"""
    data_path = Path(data_dir)

    if not data_path.exists():
        logger.warning(f"Data directory does not exist: {data_dir}")
        return None

    # Find first PDF
    pdf_files = [f for f in data_path.rglob("*.pdf") if not f.name.startswith("._")]

    if not pdf_files:
        logger.warning(f"No PDF files found in {data_dir}")
        return None

    return pdf_files[0]


def convert_pdf_to_image(
    pdf_path: Path, page_num: int = 0, dpi: int = 150
) -> Optional[str]:
    """
    Convert PDF page to temporary PNG image

    Args:
        pdf_path: Path to PDF file
        page_num: Page number to convert (0-indexed)
        dpi: DPI for rendering

    Returns:
        Path to temporary image file, or None on error
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))

        if page_num >= doc.page_count:
            logger.error(f"Page {page_num} does not exist (total: {doc.page_count})")
            return None

        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)

        temp_img = "_tmp_p0_ocr_test.png"
        pix.save(temp_img)
        doc.close()

        logger.info(
            f"✓ Converted PDF page to image: {temp_img} ({pix.width}x{pix.height} @ {dpi} DPI)"
        )
        return temp_img

    except Exception as e:
        logger.error(f"✗ PDF to image conversion failed: {e}")
        logger.exception(e)
        return None


def test_ocr_inference(gpu_info: GPUInfo, test_image: str, ocr_models_dir: str) -> dict:
    """
    Run OCR inference and measure performance

    Args:
        gpu_info: GPU information from initialization
        test_image: Path to test image
        ocr_models_dir: Directory containing OCR models

    Returns:
        Dictionary with test results
    """
    results = {
        "success": False,
        "inference_time": None,
        "regions_detected": 0,
        "sample_texts": [],
        "error": None,
        "used_gpu": gpu_info.cuda_available,
    }

    try:
        from paddleocr import PaddleOCR

        # Get OCR configuration
        use_gpu = gpu_info.cuda_available

        logger.info(f"Initializing PaddleOCR (use_gpu={use_gpu})...")

        # Model paths
        det_model = os.path.join(ocr_models_dir, "det", "PP-OCRv5_server_det_infer")
        cls_model = os.path.join(
            ocr_models_dir, "cls", "ch_ppocr_mobile_v2.0_cls_infer"
        )

        # Verify models exist
        if not os.path.isdir(det_model):
            raise FileNotFoundError(f"Detection model not found: {det_model}")
        if not os.path.isdir(cls_model):
            raise FileNotFoundError(f"Classification model not found: {cls_model}")

        # Initialize OCR
        ocr = PaddleOCR(
            lang="en",
            det_model_dir=det_model,
            cls_model_dir=cls_model,
            use_angle_cls=True,
            use_gpu=use_gpu,
            use_space_char=True,
            show_log=False,
        )

        logger.info("✓ PaddleOCR initialized")

        # Run inference
        logger.info(f"Running OCR inference on: {test_image}")
        t0 = time.time()

        ocr_result = ocr.ocr(test_image, cls=True)

        inference_time = time.time() - t0
        results["inference_time"] = inference_time

        # Parse results
        if ocr_result and ocr_result[0]:
            regions = ocr_result[0]
            results["regions_detected"] = len(regions)

            # Get sample texts (first 3)
            for i, line in enumerate(regions[:3], 1):
                text, conf = line[1]
                results["sample_texts"].append(
                    {"text": text, "confidence": float(conf)}
                )

            results["success"] = True

            logger.info(f"✓ OCR inference successful")
            logger.info(f"  Inference time: {inference_time:.2f}s")
            logger.info(f"  Regions detected: {len(regions)}")
            logger.info(f"  Sample texts:")
            for i, sample in enumerate(results["sample_texts"], 1):
                logger.info(
                    f"    {i}. '{sample['text']}' (conf: {sample['confidence']:.3f})"
                )
        else:
            logger.warning("⚠ OCR returned no text regions")
            results["error"] = "No text regions detected"

    except Exception as e:
        error_msg = f"OCR inference failed: {str(e)}"
        logger.error(f"✗ {error_msg}")
        logger.exception(e)
        results["error"] = error_msg

    return results


def run_sanity_test(prefer_gpu: bool = True, device_id: int = 0) -> bool:
    """
    Run complete OCR GPU sanity test

    Args:
        prefer_gpu: Whether to prefer GPU over CPU
        device_id: GPU device ID

    Returns:
        True if test passes, False otherwise
    """
    logger.info("=" * 70)
    logger.info("P0: OCR GPU SANITY TEST")
    logger.info("=" * 70)

    # Step 1: Initialize GPU
    logger.info("\n[Step 1/4] Initializing GPU environment...")
    gpu_info = initialize_gpu_environment(
        prefer_gpu=prefer_gpu, device_id=device_id, verbose=True
    )

    # Step 2: Find test PDF
    logger.info("\n[Step 2/4] Finding test PDF...")
    test_pdf = find_test_pdf()

    if not test_pdf:
        logger.error("✗ No test PDF found. Cannot proceed with OCR test.")
        return False

    logger.info(f"✓ Test PDF: {test_pdf.name}")

    # Step 3: Convert PDF to image
    logger.info("\n[Step 3/4] Converting PDF to image...")
    test_image = convert_pdf_to_image(test_pdf, page_num=0, dpi=150)

    if not test_image:
        logger.error("✗ PDF conversion failed. Cannot proceed with OCR test.")
        return False

    # Step 4: Run OCR inference
    logger.info("\n[Step 4/4] Running OCR inference...")

    ocr_models_dir = (
        r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"
    )

    try:
        results = test_ocr_inference(gpu_info, test_image, ocr_models_dir)

        # Print summary
        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)
        logger.info(f"GPU Available: {gpu_info.cuda_available}")
        logger.info(f"Device Used: {gpu_info.device_name}")

        if gpu_info.cuda_version:
            logger.info(f"CUDA Version: {gpu_info.cuda_version}")
        if gpu_info.cudnn_version:
            logger.info(f"cuDNN Version: {gpu_info.cudnn_version}")

        logger.info(
            f"\nOCR Test Result: {'✓ PASSED' if results['success'] else '✗ FAILED'}"
        )

        if results["success"]:
            logger.info(f"  Inference Time: {results['inference_time']:.2f}s")
            logger.info(f"  Regions Detected: {results['regions_detected']}")
            logger.info(f"  Used GPU: {results['used_gpu']}")
        else:
            logger.error(f"  Error: {results['error']}")

        if gpu_info.initialization_error:
            logger.warning(
                f"\nGPU Initialization Error: {gpu_info.initialization_error}"
            )
            logger.warning("System automatically fell back to CPU mode")

        logger.info("=" * 70)

        return results["success"]

    finally:
        # Cleanup
        if test_image and os.path.exists(test_image):
            try:
                os.remove(test_image)
                logger.info(f"✓ Cleaned up temporary image: {test_image}")
            except:
                pass


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="P0: OCR GPU Sanity Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--prefer-gpu",
        action="store_true",
        default=True,
        help="Prefer GPU over CPU (default: True)",
    )

    parser.add_argument(
        "--no-gpu", action="store_true", help="Force CPU mode (disable GPU)"
    )

    parser.add_argument(
        "--device-id", type=int, default=0, help="GPU device ID (default: 0)"
    )

    args = parser.parse_args()

    prefer_gpu = args.prefer_gpu and not args.no_gpu

    # Run test
    success = run_sanity_test(prefer_gpu=prefer_gpu, device_id=args.device_id)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
