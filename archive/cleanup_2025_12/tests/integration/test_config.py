"""
Test script for PipelineConfig

Tests:
1. Load config successfully
2. Validate all parameters
3. Check paths
4. Test OCR config generation
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import PipelineConfig, get_config


def test_pipeline_config():
    """Test PipelineConfig functionality"""

    print("=" * 80)
    print("Testing PipelineConfig Module")
    print("=" * 80)

    # Test 1: Load config
    print("\n1. Loading config...")
    config = get_config()
    print(f"✓ Config loaded successfully")
    print(config)

    # Test 2: Validate
    print("\n2. Validating config...")
    try:
        config.validate()
        print("✓ Config validation passed")
    except ValueError as e:
        print(f"✗ Config validation failed: {e}")
        return

    # Test 3: Check paths
    print("\n3. Checking paths...")
    print(f"  PROJECT_ROOT: {config.PROJECT_ROOT}")
    print(f"  ARTIFACTS_DIR: {config.ARTIFACTS_DIR}")
    print(f"  DOCUMENTS_DIR: {config.DOCUMENTS_DIR}")

    print(f"\n  Detection model exists: {config.DET_MODEL_DIR.exists()}")
    print(f"  Classifier model exists: {config.CLS_MODEL_DIR.exists()}")
    print(f"  Recognition model: {config.REC_MODEL_DIR or 'Auto-download'}")

    # Test 4: Check thresholds
    print("\n4. Checking thresholds...")
    print(f"  MIN_TEXT_LENGTH: {config.MIN_TEXT_LENGTH}")
    print(f"  OCR_TRIGGER_THRESHOLD: {config.OCR_TRIGGER_THRESHOLD}")
    print(f"  OCR_MIN_CONFIDENCE: {config.OCR_MIN_CONFIDENCE}")
    print(f"  BM25_K1: {config.BM25_K1}")
    print(f"  BM25_B: {config.BM25_B}")
    print(f"  BM25_EPSILON: {config.BM25_EPSILON}")

    # Test 5: Check artifact paths
    print("\n5. Checking artifact paths...")
    print(f"  page_bm25_index_path: {config.page_bm25_index_path}")
    print(f"  text_by_page_path: {config.text_by_page_path}")
    print(f"  page_metadata_path: {config.page_metadata_path}")
    print(f"  doc_metadata_path: {config.doc_metadata_path}")

    # Test 6: Generate OCR config
    print("\n6. Generating OCR config...")
    ocr_config = config.get_ocr_config()
    print("  OCR config parameters:")
    for key, value in ocr_config.items():
        print(f"    {key}: {value}")

    # Test 7: Singleton behavior
    print("\n7. Testing singleton behavior...")
    config2 = get_config()
    if config is config2:
        print("✓ Singleton working correctly (same instance)")
    else:
        print("✗ Singleton not working (different instances)")

    print("\n" + "=" * 80)
    print("PipelineConfig tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    test_pipeline_config()
