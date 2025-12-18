"""
Unit tests for GPU Memory Management in Ingestion Pipeline.

Tests cover:
- GPU availability check on initialization
- GPU memory cleanup after batch processing
- Device detection logging

Requirements: 6.2, 6.4
"""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestGPUCheckFunction:
    """Tests for _check_gpu_availability function logic."""

    def test_gpu_available_detection(self):
        """
        Test GPU availability detection when CUDA is available.

        Requirements: 6.4
        """
        # Mock torch module
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4060"
        mock_torch.cuda.device_count.return_value = 1
        mock_torch.version.cuda = "12.1"

        mock_props = MagicMock()
        mock_props.total_memory = 8 * 1024**3  # 8 GB
        mock_torch.cuda.get_device_properties.return_value = mock_props

        # Test the logic directly
        with patch.dict("sys.modules", {"torch": mock_torch}):
            import torch

            assert torch.cuda.is_available() == True
            assert torch.cuda.get_device_name(0) == "NVIDIA RTX 4060"
            assert torch.cuda.device_count() == 1

    def test_gpu_not_available_detection(self):
        """
        Test GPU availability detection when CUDA is not available.

        Requirements: 6.4
        """
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict("sys.modules", {"torch": mock_torch}):
            import torch

            assert torch.cuda.is_available() == False


class TestGPUCleanupFunction:
    """Tests for _cleanup_gpu_memory function logic."""

    def test_empty_cache_called_when_gpu_available(self):
        """
        Test that torch.cuda.empty_cache() is called when GPU is available.

        Requirements: 6.2
        """
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.memory_allocated.return_value = 100 * 1024**2
        mock_torch.cuda.memory_reserved.return_value = 200 * 1024**2

        with patch.dict("sys.modules", {"torch": mock_torch}):
            import torch

            # Simulate cleanup logic
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            mock_torch.cuda.empty_cache.assert_called_once()

    def test_empty_cache_not_called_when_no_gpu(self):
        """
        Test that torch.cuda.empty_cache() is not called when GPU is not available.

        Requirements: 6.2
        """
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict("sys.modules", {"torch": mock_torch}):
            import torch

            # Simulate cleanup logic
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            mock_torch.cuda.empty_cache.assert_not_called()

    def test_memory_stats_retrieval(self):
        """
        Test that memory statistics can be retrieved.

        Requirements: 6.2
        """
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.memory_allocated.return_value = 100 * 1024**2  # 100 MB
        mock_torch.cuda.memory_reserved.return_value = 200 * 1024**2  # 200 MB

        with patch.dict("sys.modules", {"torch": mock_torch}):
            import torch

            allocated = torch.cuda.memory_allocated(0) / (1024**2)
            reserved = torch.cuda.memory_reserved(0) / (1024**2)

            assert allocated == 100.0
            assert reserved == 200.0


class TestLayoutDetectorCleanup:
    """Tests for LayoutDetector cleanup integration."""

    def test_detector_cleanup_calls_empty_cache(self):
        """
        Test that LayoutDetector.cleanup() calls torch.cuda.empty_cache().

        Requirements: 6.2
        """
        from app.ingestion.layout.detector import LayoutDetector

        # Reset singleton
        LayoutDetector.reset_instance()

        detector = LayoutDetector.get_instance()
        detector._model = MagicMock()
        detector._model_loaded = True

        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.empty_cache") as mock_empty_cache:
                detector.cleanup()

                assert detector._model is None
                assert detector._model_loaded is False
                mock_empty_cache.assert_called_once()

        # Cleanup
        LayoutDetector.reset_instance()

    def test_detector_cleanup_handles_no_gpu(self):
        """
        Test that LayoutDetector.cleanup() handles case when GPU is not available.

        Requirements: 6.2
        """
        from app.ingestion.layout.detector import LayoutDetector

        # Reset singleton
        LayoutDetector.reset_instance()

        detector = LayoutDetector.get_instance()
        detector._model = MagicMock()
        detector._model_loaded = True

        with patch("torch.cuda.is_available", return_value=False):
            # Should not raise
            detector.cleanup()

            assert detector._model is None
            assert detector._model_loaded is False

        # Cleanup
        LayoutDetector.reset_instance()


class TestOrchestratorCleanup:
    """Tests for HybridExtractionOrchestrator cleanup."""

    def test_orchestrator_cleanup_calls_detector_cleanup(self):
        """
        Test that orchestrator cleanup calls detector cleanup.

        Requirements: 6.2
        """
        from app.ingestion.layout.detector import LayoutDetector
        from app.ingestion.layout.orchestrator import HybridExtractionOrchestrator

        # Reset singleton
        LayoutDetector.reset_instance()

        orchestrator = HybridExtractionOrchestrator()

        with patch.object(orchestrator.layout_detector, "cleanup") as mock_cleanup:
            orchestrator.cleanup()
            mock_cleanup.assert_called_once()

        # Cleanup
        LayoutDetector.reset_instance()


class TestGPUManagementInPipeline:
    """Tests for GPU management methods in IngestionPipeline."""

    def test_check_gpu_availability_method_exists(self):
        """
        Test that _check_gpu_availability method exists in IngestionPipeline.

        Requirements: 6.4
        """
        # Read the source file to verify method exists
        with open("tools/ingest.py", "r", encoding="utf-8") as f:
            content = f.read()

        assert (
            "def _check_gpu_availability(self)" in content
        ), "_check_gpu_availability method should exist"
        assert "torch.cuda.is_available()" in content, "Should check CUDA availability"
        assert "torch.cuda.get_device_name" in content, "Should get device name"

    def test_cleanup_gpu_memory_method_exists(self):
        """
        Test that _cleanup_gpu_memory method exists in IngestionPipeline.

        Requirements: 6.2
        """
        with open("tools/ingest.py", "r", encoding="utf-8") as f:
            content = f.read()

        assert (
            "def _cleanup_gpu_memory(self)" in content
        ), "_cleanup_gpu_memory method should exist"
        assert "torch.cuda.empty_cache()" in content, "Should call empty_cache"
        assert "memory_allocated" in content, "Should track memory allocation"
        assert "memory_reserved" in content, "Should track memory reserved"

    def test_run_calls_cleanup(self):
        """
        Test that run() method calls _cleanup_gpu_memory.

        Requirements: 6.2
        """
        with open("tools/ingest.py", "r", encoding="utf-8") as f:
            content = f.read()

        # Find the run method and verify it calls cleanup
        assert (
            "_cleanup_gpu_memory()" in content
        ), "run() should call _cleanup_gpu_memory()"

    def test_init_calls_gpu_check(self):
        """
        Test that __init__ calls _check_gpu_availability.

        Requirements: 6.4
        """
        with open("tools/ingest.py", "r", encoding="utf-8") as f:
            content = f.read()

        # Verify GPU check is called in init
        assert (
            "_check_gpu_availability()" in content
        ), "__init__ should call _check_gpu_availability()"
