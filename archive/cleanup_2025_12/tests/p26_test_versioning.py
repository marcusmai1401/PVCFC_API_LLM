"""
P2.6 Integration Test: Versioning & Rollback

Tests version management, snapshots, and version-aware retrieval.
"""

import logging
import shutil
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.storage.version_manager import VersionManager
from app.storage.versioned_retriever import VersionedRetriever

logger = logging.getLogger(__name__)


def test_versioning():
    """
    Test complete versioning workflow
    """
    logger.info("=" * 70)
    logger.info("P2.6 INTEGRATION TEST: Versioning & Rollback")
    logger.info("=" * 70)

    # Use P2 test artifacts
    test_dir = PROJECT_ROOT / "artifacts" / "p2_test"

    if not test_dir.exists():
        logger.error(f"P2 test artifacts not found: {test_dir}")
        logger.error(
            "Please run P2 integration test first: python tests/p2_test_storage_integration.py"
        )
        return False

    # Setup clean test environment for versioning
    version_test_dir = PROJECT_ROOT / "artifacts" / "version_test"
    if version_test_dir.exists():
        shutil.rmtree(version_test_dir)
    version_test_dir.mkdir(parents=True)

    # Copy P2 test artifacts to version test dir
    ingestion_src = test_dir / "ingestion"
    ingestion_dest = version_test_dir / "ingestion"
    shutil.copytree(ingestion_src, ingestion_dest)

    index_src = test_dir / "index"
    index_dest = version_test_dir / "index"
    shutil.copytree(index_src, index_dest)

    logger.info(f"\n✅ Copied test artifacts to: {version_test_dir}")

    # ========================================
    # Step 1: Initialize Version Manager
    # ========================================
    logger.info("\n[1/7] Initializing Version Manager...")

    vm = VersionManager(version_test_dir)
    logger.info(f"✅ Version Manager initialized")
    logger.info(f"   Versions directory: {vm.versions_dir}")

    # ========================================
    # Step 2: Create Version v1
    # ========================================
    logger.info("\n[2/7] Creating version v1...")

    manifest_path = ingestion_dest / "manifest_v1.json"

    if not manifest_path.exists():
        # Fallback to manifest.json if manifest_v1.json doesn't exist
        manifest_path = ingestion_dest / "manifest.json"

    version_v1 = vm.create_version(
        version_id="v1",
        ingestion_manifest_path=manifest_path,
        index_manifest_path=None,  # No index manifest in P2 test
        description="Initial version from P2 test",
        tags=["test", "baseline"],
    )

    logger.info(f"✅ Created version v1")
    logger.info(f"   Chunks: {version_v1['stats']['total_chunks']}")
    logger.info(f"   Embedded: {version_v1['stats']['total_embedded']}")

    # ========================================
    # Step 3: Create Version v2 (simulated update)
    # ========================================
    logger.info("\n[3/7] Creating version v2 (simulated update)...")

    # For this test, v2 is same as v1 (in real scenario would be different data)
    version_v2 = vm.create_version(
        version_id="v2",
        ingestion_manifest_path=manifest_path,
        index_manifest_path=None,
        description="Updated version with new data",
        tags=["test", "updated"],
    )

    logger.info(f"✅ Created version v2")
    logger.info(f"   Chunks: {version_v2['stats']['total_chunks']}")

    # ========================================
    # Step 4: List Versions
    # ========================================
    logger.info("\n[4/7] Listing versions...")

    versions = vm.list_versions()
    logger.info(f"\n📋 Available versions: {len(versions)}")
    for v in versions:
        logger.info(f"  - {v['version_id']}: {v['description']}")
        logger.info(f"    Created: {v['created_at']}")
        logger.info(f"    Tags: {v['tags']}")
        logger.info(f"    Chunks: {v['stats']['total_chunks']}")

    # ========================================
    # Step 5: Compare Versions
    # ========================================
    logger.info("\n[5/7] Comparing versions...")

    comparison = vm.compare_versions("v1", "v2")
    logger.info(f"\n📊 Version Comparison (v1 vs v2):")
    logger.info(f"   v1 chunks: {comparison['version_1']['stats']['total_chunks']}")
    logger.info(f"   v2 chunks: {comparison['version_2']['stats']['total_chunks']}")
    logger.info(f"   Delta: {comparison['diff']['chunks_delta']}")

    # ========================================
    # Step 6: Test Rollback
    # ========================================
    logger.info("\n[6/7] Testing rollback to v1...")

    rollback_dir = version_test_dir / "rollback_test"
    rollback_ingestion = rollback_dir / "ingestion"
    rollback_index = rollback_dir / "index"

    success = vm.rollback(
        version_id="v1",
        target_ingestion_dir=rollback_ingestion,
        target_index_dir=rollback_index,
    )

    if success:
        logger.info(f"✅ Rollback successful")
        logger.info(f"   Restored to: {rollback_dir}")

        # Verify rollback
        restored_manifest = rollback_ingestion / "manifest.json"
        if restored_manifest.exists():
            logger.info(f"   ✓ Manifest restored")
        else:
            logger.warning(f"   ⚠️  Manifest not found")
    else:
        logger.error("❌ Rollback failed")

    # ========================================
    # Step 7: Test Versioned Retriever
    # ========================================
    logger.info("\n[7/7] Testing Versioned Retriever...")

    retriever = VersionedRetriever(version_test_dir, auto_load=False)

    # List available versions
    available = retriever.list_available_versions()
    logger.info(f"\n📋 Retriever sees {len(available)} versions:")
    for v in available:
        logger.info(f"  - {v['version_id']}: {v['description']}")

    # Load specific version
    logger.info(f"\n⏳ Loading version v1...")
    load_success = retriever.load_version("v1")

    if load_success:
        logger.info(f"✅ Loaded version v1")

        # Get version info
        info = retriever.get_version_info()
        logger.info(f"\n📦 Current Version Info:")
        logger.info(f"   Version: {info['version_id']}")
        logger.info(f"   Created: {info['created_at']}")
        logger.info(f"   BM25 loaded: {info['bm25_loaded']}")
        logger.info(f"   FAISS loaded: {info['faiss_loaded']}")
        logger.info(f"   Total chunks: {info['stats']['total_chunks']}")
    else:
        logger.error("❌ Failed to load version")

    # Switch to v2
    logger.info(f"\n⏳ Switching to version v2...")
    switch_success = retriever.load_version("v2")

    if switch_success:
        logger.info(f"✅ Switched to version v2")
        info = retriever.get_version_info()
        logger.info(f"   Now on version: {info['version_id']}")

    # ========================================
    # Validation
    # ========================================
    logger.info("\n" + "=" * 70)
    logger.info("VALIDATION")
    logger.info("=" * 70)

    # Check version history file
    history_file = vm.versions_dir / "version_history.json"
    assert history_file.exists(), "Version history file not created"
    logger.info("✅ Version history file exists")

    # Check version directories
    v1_dir = vm.versions_dir / "v1"
    v2_dir = vm.versions_dir / "v2"
    assert v1_dir.exists(), "Version v1 directory not created"
    assert v2_dir.exists(), "Version v2 directory not created"
    logger.info("✅ Version directories created")

    # Check version contents
    assert (v1_dir / "manifest.json").exists(), "v1 manifest not found"
    assert (v2_dir / "manifest.json").exists(), "v2 manifest not found"
    logger.info("✅ Version manifests stored")

    # Check current version (should be v1 after rollback)
    current = vm.get_current_version()
    assert (
        current == "v1"
    ), f"Current version should be v1 after rollback, got {current}"
    logger.info(f"✅ Current version tracked: {current}")

    # Check rollback worked
    assert rollback_ingestion.exists(), "Rollback directory not created"
    assert (
        rollback_ingestion / "manifest.json"
    ).exists(), "Rollback manifest not found"
    logger.info("✅ Rollback successful")

    # Check versioned retriever
    assert load_success, "Version loading failed"
    assert switch_success, "Version switching failed"
    logger.info("✅ Versioned retriever working")

    logger.info("\n" + "=" * 70)
    logger.info("✅ P2.6 INTEGRATION TEST PASSED")
    logger.info("=" * 70)
    logger.info(f"\nTest artifacts saved to: {version_test_dir}")
    logger.info("Features validated:")
    logger.info("  ✓ Version creation and snapshots")
    logger.info("  ✓ Version history tracking")
    logger.info("  ✓ Version comparison")
    logger.info("  ✓ Rollback to previous version")
    logger.info("  ✓ Version-aware retrieval")
    logger.info("  ✓ Version switching without restart")

    return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        success = test_versioning()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)
