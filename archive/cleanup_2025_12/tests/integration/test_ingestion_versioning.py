"""
Integration Test for Ingestion-Versioning
Tests the complete workflow of ingestion with automatic version creation
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

import pytest
from loguru import logger

from app.storage.version_manager import VersionManager
from tools.ingest import IngestionPipeline


class TestIngestionVersioning:
    """Test suite for ingestion-versioning integration"""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing"""
        temp_dir = Path(tempfile.mkdtemp(prefix="test_ingest_version_"))

        # Create test PDF directory with some dummy content
        source_dir = temp_dir / "test_pdfs"
        source_dir.mkdir()

        # Create output directory
        output_dir = temp_dir / "ingestion_output"

        # Create artifacts base
        artifacts_dir = temp_dir / "artifacts"
        artifacts_dir.mkdir()

        yield {
            "temp_dir": temp_dir,
            "source_dir": source_dir,
            "output_dir": output_dir,
            "artifacts_dir": artifacts_dir,
        }

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_ingestion_without_versioning(self, temp_workspace):
        """Test normal ingestion without version creation"""
        logger.info("Test 1: Ingestion without versioning")

        pipeline = IngestionPipeline(
            source_dir=temp_workspace["source_dir"],
            output_dir=temp_workspace["output_dir"],
            workers=1,
            create_version=False,  # No versioning
        )

        # Note: This will fail if no PDFs, but tests the pipeline structure
        # For real test, would need sample PDFs

        # Verify versioning is disabled
        assert pipeline.create_version is False
        assert pipeline.version_id is None

        logger.info("✅ Test 1 passed: Pipeline initialized without versioning")

    def test_ingestion_with_versioning_config(self, temp_workspace):
        """Test ingestion pipeline with versioning configuration"""
        logger.info("Test 2: Ingestion with versioning configuration")

        version_id = "test_v1.0"
        description = "Test version"
        tags = ["test", "integration"]

        pipeline = IngestionPipeline(
            source_dir=temp_workspace["source_dir"],
            output_dir=temp_workspace["output_dir"],
            workers=1,
            create_version=True,
            version_id=version_id,
            version_description=description,
            version_tags=tags,
        )

        # Verify versioning configuration
        assert pipeline.create_version is True
        assert pipeline.version_id == version_id
        assert pipeline.version_description == description
        assert pipeline.version_tags == tags

        logger.info("✅ Test 2 passed: Versioning configuration correct")

    def test_manifest_generation(self, temp_workspace):
        """Test ingestion manifest generation"""
        logger.info("Test 3: Manifest generation")

        pipeline = IngestionPipeline(
            source_dir=temp_workspace["source_dir"],
            output_dir=temp_workspace["output_dir"],
            workers=1,
            create_version=True,
            version_id="test_manifest",
        )

        # Setup output directory
        pipeline._setup_output_dirs()

        # Simulate some stats
        pipeline.stats = {
            "total_pdfs": 10,
            "processed": 8,
            "quarantine_count": 2,
            "total_chunks": 250,
        }

        # Generate manifest
        manifest_path = pipeline._write_ingestion_manifest()

        # Verify manifest exists
        assert manifest_path.exists()

        # Verify manifest content
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "ingestion_id" in manifest
        assert "config" in manifest
        assert "source" in manifest
        assert "chunks" in manifest
        assert manifest["chunks"]["total_chunks"] == 250
        assert manifest["source"]["processed_files"] == 8

        logger.info("✅ Test 3 passed: Manifest generation works correctly")

    def test_version_manager_integration(self, temp_workspace):
        """Test version manager integration"""
        logger.info("Test 4: Version manager integration")

        # Create a mock manifest WITHOUT artifacts to avoid path issues in test
        # The version manager will simply skip copying artifacts if they don't exist
        output_dir = temp_workspace["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "manifest.json"

        manifest = {
            "version": "1.0.0",
            "ingestion_id": "test_run_001",
            "created_at": "2025-01-02T12:00:00Z",
            "config": {"chunk_size": 1000},
            "source": {"total_files": 5, "processed_files": 5},
            "chunks": {"total_chunks": 100, "unique_chunks": 100},
            "embeddings": {"total_embedded": 0},
            "artifacts": {},
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Initialize version manager
        vm = VersionManager(temp_workspace["artifacts_dir"])

        # Create version
        version_meta = vm.create_version(
            version_id="test_v1.0",
            ingestion_manifest_path=manifest_path,
            description="Test version",
            tags=["test"],
        )

        # Verify version created
        assert version_meta["version_id"] == "test_v1.0"
        assert version_meta["stats"]["total_chunks"] == 100

        # Verify version can be retrieved
        retrieved = vm.get_version("test_v1.0")
        assert retrieved is not None
        assert retrieved["version_id"] == "test_v1.0"

        # Verify version directory exists
        version_dir = temp_workspace["artifacts_dir"] / "versions" / "test_v1.0"
        assert version_dir.exists()

        logger.info("✅ Test 4 passed: Version manager integration works")

    def test_version_listing_and_comparison(self, temp_workspace):
        """Test version listing and comparison"""
        logger.info("Test 5: Version listing and comparison")

        # Create two test versions
        vm = VersionManager(temp_workspace["artifacts_dir"])

        for i, version_id in enumerate(["v1.0", "v1.1"]):
            manifest_path = temp_workspace["output_dir"] / f"manifest_{version_id}.json"
            manifest = {
                "version": "1.0.0",
                "ingestion_id": f"test_{version_id}",
                "created_at": "2025-01-02T12:00:00Z",
                "config": {},
                "source": {"total_files": 5},
                "chunks": {
                    "total_chunks": 100 + (i * 50),
                    "unique_chunks": 100 + (i * 50),
                },
                "embeddings": {"total_embedded": 0},
                "artifacts": {},
            }

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            vm.create_version(
                version_id=version_id,
                ingestion_manifest_path=manifest_path,
                description=f"Version {version_id}",
                tags=["test"],
            )

        # List versions
        versions = vm.list_versions()
        assert len(versions) >= 2

        # Compare versions
        comparison = vm.compare_versions("v1.0", "v1.1")
        assert "diff" in comparison
        assert comparison["diff"]["chunks_delta"] == 50

        logger.info("✅ Test 5 passed: Version listing and comparison work")


def run_integration_tests():
    """Run integration tests"""
    logger.info("=" * 80)
    logger.info("INGESTION-VERSIONING INTEGRATION TESTS")
    logger.info("=" * 80)

    # Create test instance
    test_suite = TestIngestionVersioning()

    # Create temp workspace
    import tempfile

    temp_dir = Path(tempfile.mkdtemp(prefix="test_ingest_version_"))

    workspace = {
        "temp_dir": temp_dir,
        "source_dir": temp_dir / "test_pdfs",
        "output_dir": temp_dir / "ingestion_output",
        "artifacts_dir": temp_dir / "artifacts",
    }

    workspace["source_dir"].mkdir()
    workspace["artifacts_dir"].mkdir()

    try:
        # Run tests
        logger.info("")
        test_suite.test_ingestion_without_versioning(workspace)

        logger.info("")
        test_suite.test_ingestion_with_versioning_config(workspace)

        logger.info("")
        test_suite.test_manifest_generation(workspace)

        logger.info("")
        test_suite.test_version_manager_integration(workspace)

        logger.info("")
        test_suite.test_version_listing_and_comparison(workspace)

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ ALL INTEGRATION TESTS PASSED")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
