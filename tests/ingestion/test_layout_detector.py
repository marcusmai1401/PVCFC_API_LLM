"""
Unit tests and property tests for LayoutDetector.

Tests cover:
- Property 1: Singleton Model Instance
- Property 9: Valid Region Labels
- Error handling and fallback behavior

Requirements: 1.2, 1.3, 1.4, 6.1, 6.3
"""

from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ingestion.layout import LayoutDetector, LayoutRegion, RegionLabel


class TestLayoutDetectorSingleton:
    """Tests for singleton pattern implementation."""

    def setup_method(self):
        """Reset singleton before each test."""
        LayoutDetector.reset_instance()

    def teardown_method(self):
        """Cleanup after each test."""
        LayoutDetector.reset_instance()

    def test_singleton_same_instance(self):
        """
        **Feature: hybrid-layout-extraction, Property 1: Singleton Model Instance**

        Verify that multiple calls to get_instance() return the same object.
        **Validates: Requirements 1.4, 6.1**
        """
        instance1 = LayoutDetector.get_instance()
        instance2 = LayoutDetector.get_instance()
        instance3 = LayoutDetector()

        assert instance1 is instance2, "get_instance() should return same instance"
        assert (
            instance1 is instance3
        ), "Direct instantiation should return same instance"

    @settings(max_examples=100)
    @given(num_calls=st.integers(min_value=2, max_value=20))
    def test_singleton_property_multiple_calls(self, num_calls: int):
        """
        **Feature: hybrid-layout-extraction, Property 1: Singleton Model Instance**

        For any number of calls to get_instance(), the returned instance
        SHALL be the same object (identity equality).
        **Validates: Requirements 1.4, 6.1**
        """
        # Reset for each hypothesis example
        LayoutDetector.reset_instance()

        instances = [LayoutDetector.get_instance() for _ in range(num_calls)]

        # All instances should be identical
        first_instance = instances[0]
        for i, instance in enumerate(instances[1:], start=2):
            assert instance is first_instance, f"Call {i} returned different instance"

    def test_singleton_thread_safety(self):
        """Test that singleton is thread-safe."""
        import threading

        instances = []
        errors = []

        def get_instance():
            try:
                instance = LayoutDetector.get_instance()
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(instances) == 10

        # All instances should be the same
        first = instances[0]
        for inst in instances[1:]:
            assert inst is first


class TestLayoutDetectorLabels:
    """Tests for region label validation."""

    def setup_method(self):
        """Reset singleton before each test."""
        LayoutDetector.reset_instance()

    def teardown_method(self):
        """Cleanup after each test."""
        LayoutDetector.reset_instance()

    def test_valid_region_labels_enum(self):
        """
        **Feature: hybrid-layout-extraction, Property 9: Valid Region Labels**

        Verify all RegionLabel enum values are valid.
        **Validates: Requirements 1.2**
        """
        expected_labels = {
            "Section_Header",
            "Title",
            "Table",
            "Text",
            "List",
            "Caption",
            "Footnote",
            "Page_Footer",
        }

        actual_labels = set(RegionLabel.get_all_values())

        assert actual_labels == expected_labels

    @settings(max_examples=100)
    @given(label=st.sampled_from(RegionLabel.get_all_values()))
    def test_region_label_is_valid(self, label: str):
        """
        **Feature: hybrid-layout-extraction, Property 9: Valid Region Labels**

        For any region label from the enum, it SHALL be recognized as valid.
        **Validates: Requirements 1.2**
        """
        assert RegionLabel.is_valid(label)

    def test_label_mapping_coverage(self):
        """Test that all expected Surya labels are mapped."""
        detector = LayoutDetector.get_instance()

        # Test common Surya labels
        test_cases = [
            ("SectionHeader", RegionLabel.SECTION_HEADER.value),
            ("Title", RegionLabel.TITLE.value),
            ("Table", RegionLabel.TABLE.value),
            ("Text", RegionLabel.TEXT.value),
            ("Paragraph", RegionLabel.TEXT.value),
            ("List-item", RegionLabel.LIST.value),
            ("Caption", RegionLabel.CAPTION.value),
            ("Footnote", RegionLabel.FOOTNOTE.value),
            ("Footer", RegionLabel.PAGE_FOOTER.value),
        ]

        for surya_label, expected in test_cases:
            result = detector._map_label(surya_label)
            assert (
                result == expected
            ), f"Label '{surya_label}' should map to '{expected}', got '{result}'"

    def test_unknown_label_defaults_to_text(self):
        """Test that unknown labels default to TEXT."""
        detector = LayoutDetector.get_instance()

        unknown_labels = ["Unknown", "RandomLabel", "Figure", "Image"]

        for label in unknown_labels:
            result = detector._map_label(label)
            assert (
                result == RegionLabel.TEXT.value
            ), f"Unknown label '{label}' should default to TEXT"


class TestLayoutDetectorErrorHandling:
    """Tests for error handling and fallback behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        LayoutDetector.reset_instance()

    def teardown_method(self):
        """Cleanup after each test."""
        LayoutDetector.reset_instance()

    def test_detect_layout_returns_empty_on_model_load_failure(self):
        """
        Test that detect_layout returns empty list when model fails to load.

        Requirements: 1.3, 6.3
        """
        detector = LayoutDetector.get_instance()

        # Mock _load_model to return False
        with patch.object(detector, "_load_model", return_value=False):
            # Create a simple test image
            import io

            from PIL import Image

            img = Image.new("RGB", (100, 100), color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes = img_bytes.getvalue()

            result = detector.detect_layout(img_bytes)

            assert result == [], "Should return empty list on model load failure"

    def test_detect_layout_returns_empty_on_cuda_oom(self):
        """
        Test that detect_layout returns empty list on CUDA OOM error.

        Requirements: 1.3, 6.3
        """
        detector = LayoutDetector.get_instance()
        detector._model_loaded = True
        detector._model = MagicMock()

        # Mock torch.cuda.OutOfMemoryError
        import torch

        detector._model.side_effect = torch.cuda.OutOfMemoryError("CUDA out of memory")

        import io

        from PIL import Image

        img = Image.new("RGB", (100, 100), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()

        result = detector.detect_layout(img_bytes)

        assert result == [], "Should return empty list on CUDA OOM"

    def test_detect_layout_returns_empty_on_runtime_error(self):
        """
        Test that detect_layout returns empty list on RuntimeError.

        Requirements: 1.3, 6.3
        """
        detector = LayoutDetector.get_instance()
        detector._model_loaded = True
        detector._model = MagicMock()
        detector._model.side_effect = RuntimeError("Model error")

        import io

        from PIL import Image

        img = Image.new("RGB", (100, 100), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()

        result = detector.detect_layout(img_bytes)

        assert result == [], "Should return empty list on RuntimeError"

    def test_cleanup_releases_resources(self):
        """Test that cleanup properly releases resources."""
        detector = LayoutDetector.get_instance()
        detector._model = MagicMock()
        detector._model_loaded = True

        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.empty_cache") as mock_empty_cache:
                detector.cleanup()

                assert detector._model is None
                assert detector._model_loaded is False
                mock_empty_cache.assert_called_once()


class TestLayoutRegionValidation:
    """Tests for LayoutRegion dataclass validation."""

    def test_valid_bbox_accepted(self):
        """Test that valid bounding boxes are accepted."""
        region = LayoutRegion(
            bbox=(0.1, 0.2, 0.5, 0.6), label=RegionLabel.TEXT.value, confidence=0.95
        )

        assert region.bbox == (0.1, 0.2, 0.5, 0.6)
        assert region.label == "Text"

    def test_out_of_bounds_bbox_clamped(self):
        """Test that out-of-bounds bbox values are clamped."""
        region = LayoutRegion(
            bbox=(-0.1, -0.2, 1.5, 1.6), label=RegionLabel.TEXT.value, confidence=0.95
        )

        # Values should be clamped to 0-1 range
        assert region.bbox[0] >= 0
        assert region.bbox[1] >= 0
        assert region.bbox[2] <= 1
        assert region.bbox[3] <= 1

    def test_invalid_label_defaults_to_text(self):
        """Test that invalid labels default to TEXT."""
        region = LayoutRegion(
            bbox=(0.1, 0.2, 0.5, 0.6), label="InvalidLabel", confidence=0.95
        )

        assert region.label == RegionLabel.TEXT.value

    @settings(max_examples=100)
    @given(
        x0=st.floats(min_value=0, max_value=0.5),
        y0=st.floats(min_value=0, max_value=0.5),
        x1=st.floats(min_value=0.5, max_value=1.0),
        y1=st.floats(min_value=0.5, max_value=1.0),
        label=st.sampled_from(RegionLabel.get_all_values()),
        confidence=st.floats(min_value=0, max_value=1),
    )
    def test_layout_region_properties(self, x0, y0, x1, y1, label, confidence):
        """
        **Feature: hybrid-layout-extraction, Property 9: Valid Region Labels**

        For any LayoutRegion created with valid inputs, the label SHALL
        remain a valid RegionLabel value.
        **Validates: Requirements 1.2**
        """
        region = LayoutRegion(bbox=(x0, y0, x1, y1), label=label, confidence=confidence)

        # Label should always be valid
        assert RegionLabel.is_valid(region.label)

        # Bbox should be normalized
        assert 0 <= region.bbox[0] <= 1
        assert 0 <= region.bbox[1] <= 1
        assert 0 <= region.bbox[2] <= 1
        assert 0 <= region.bbox[3] <= 1

        # Width and height should be non-negative
        assert region.width >= 0
        assert region.height >= 0
        assert region.area >= 0
