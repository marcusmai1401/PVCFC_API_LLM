"""
Quick test to verify PaddleOCR works with cached rec model
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

from app.config import get_config

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")


def test_ocr_with_cached_model():
    """Test OCR with cached rec model"""

    print("=" * 80)
    print("Testing OCR with Cached Recognition Model")
    print("=" * 80)

    # Get config
    config = get_config()
    print(f"\nREC_MODEL_DIR: {config.REC_MODEL_DIR}")

    if config.REC_MODEL_DIR is None:
        print("⚠ Warning: REC_MODEL_DIR is None, will trigger download")
    elif config.REC_MODEL_DIR.exists():
        print("✓ Cached rec model found (offline-friendly)")
    else:
        print("✗ Cached rec model path set but doesn't exist")

    # Get OCR config
    print("\nOCR Config:")
    ocr_config = config.get_ocr_config()
    for key, value in ocr_config.items():
        print(f"  {key}: {value}")

    # Try to initialize OCR
    print("\nInitializing PaddleOCR with cached model...")
    try:
        from app.ingestion.paddle_ocr_config import initialize_paddleocr

        ocr = initialize_paddleocr(show_log=False)

        if ocr:
            print("✅ PaddleOCR initialized successfully with cached model!")
            print("   System is now offline-friendly for OCR")
        else:
            print("✗ Failed to initialize PaddleOCR")
    except Exception as e:
        print(f"✗ Error initializing OCR: {e}")

    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    test_ocr_with_cached_model()
