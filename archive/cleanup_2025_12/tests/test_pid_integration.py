"""
Test P&ID Tag Extraction Integration in Ingestion Pipeline

This test verifies that P&ID tag extraction is properly integrated
into the main ingestion pipeline without breaking existing functionality.
"""
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.ingest import IngestionPipeline


def test_pipeline_initialization_without_pid_tags():
    """Test that pipeline initializes correctly WITHOUT P&ID tags enabled"""
    pipeline = IngestionPipeline(
        source_dir=Path("data"),
        output_dir=Path("artifacts/test"),
        workers=1,
        enable_pid_tags=False,  # Disabled
    )

    assert pipeline.enable_pid_tags is False
    assert pipeline.tag_orchestrator is None
    assert "pid_docs_processed" in pipeline.stats
    assert "pid_tags_extracted" in pipeline.stats


def test_pipeline_initialization_with_pid_tags():
    """Test that pipeline initializes correctly WITH P&ID tags enabled"""
    pipeline = IngestionPipeline(
        source_dir=Path("data"),
        output_dir=Path("artifacts/test"),
        workers=1,
        enable_pid_tags=True,  # Enabled
    )

    # Should be enabled if components are available
    if pipeline.enable_pid_tags:
        assert pipeline.tag_orchestrator is not None
        assert "pid_docs_processed" in pipeline.stats
        assert "pid_tags_extracted" in pipeline.stats
    else:
        # Components not available, gracefully disabled
        assert pipeline.tag_orchestrator is None


def test_pid_stats_initialization():
    """Test that P&ID stats are properly initialized"""
    pipeline = IngestionPipeline(
        source_dir=Path("data"),
        output_dir=Path("artifacts/test"),
        workers=1,
        enable_pid_tags=True,
    )

    # Verify P&ID stats exist and are initialized to 0
    assert pipeline.stats["pid_docs_processed"] == 0
    assert pipeline.stats["pid_tags_extracted"] == 0


def test_backward_compatibility():
    """Test that existing code without enable_pid_tags still works"""
    # Create pipeline without specifying enable_pid_tags (should default to False)
    pipeline = IngestionPipeline(
        source_dir=Path("data"),
        output_dir=Path("artifacts/test"),
        workers=1,
    )

    # Should work without issues
    assert pipeline.enable_pid_tags is False
    assert pipeline.tag_orchestrator is None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
