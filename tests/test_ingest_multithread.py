"""
Test multithreaded ingestion pipeline
Tests that multithreaded PDF processing produces same results as sequential
"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

import pytest

from app.ingestion.pdf_processor import PDFDocument, PDFProcessor

# Test data location
DATA_DIR = Path("data/raw/phase1_pilot")


def _process_single_pdf(pdf_path: Path, enable_ocr: bool = False) -> PDFDocument:
    """
    Process a single PDF in isolation (thread-safe)
    Each thread gets its own PDFProcessor instance to avoid shared state issues
    """
    processor = PDFProcessor(
        enable_ocr=enable_ocr, ocr_language="eng", ocr_min_confidence=30.0
    )
    return processor.process_pdf(pdf_path)


def _get_document_signature(doc: PDFDocument) -> tuple:
    """
    Get a comparable signature of a processed document
    Used to verify that sequential vs threaded processing produces identical results
    """
    return (
        doc.file_name,
        doc.num_pages,
        doc.total_chars,
        doc.total_words,
        doc.source_format,
        len(doc.pages),
        # First page text preview for content verification
        doc.pages[0].text[:100] if doc.pages else "",
        # Last page text preview
        doc.pages[-1].text[:100] if doc.pages else "",
    )


@pytest.mark.skipif(not DATA_DIR.exists(), reason="Sample PDF directory not found")
def test_sequential_vs_threaded_processing_identical_results():
    """
    Test that sequential and threaded processing produce identical results
    This ensures thread safety and correctness of the ingestion pipeline
    """
    # Get sample PDFs (limit to 2-3 for test speed)
    pdf_files = list(DATA_DIR.rglob("*.pdf"))[:3]

    if not pdf_files:
        pytest.skip("No sample PDF files found for testing")

    print(f"Testing with {len(pdf_files)} PDF files")

    # Sequential processing
    sequential_docs = []
    for pdf_path in pdf_files:
        try:
            doc = _process_single_pdf(pdf_path)
            sequential_docs.append(doc)
        except Exception as e:
            pytest.fail(f"Sequential processing failed for {pdf_path}: {e}")

    # Threaded processing
    threaded_docs = []
    with ThreadPoolExecutor(max_workers=min(4, len(pdf_files))) as executor:
        # Submit all tasks
        future_to_path = {
            executor.submit(_process_single_pdf, pdf_path): pdf_path
            for pdf_path in pdf_files
        }

        # Collect results
        for future in as_completed(future_to_path):
            pdf_path = future_to_path[future]
            try:
                doc = future.result()
                threaded_docs.append(doc)
            except Exception as e:
                pytest.fail(f"Threaded processing failed for {pdf_path}: {e}")

    # Verify we got same number of documents
    assert len(sequential_docs) == len(threaded_docs)

    # Sort both lists by filename for comparison
    sequential_sigs = sorted([_get_document_signature(doc) for doc in sequential_docs])
    threaded_sigs = sorted([_get_document_signature(doc) for doc in threaded_docs])

    # Compare signatures - should be identical
    assert (
        sequential_sigs == threaded_sigs
    ), "Sequential and threaded processing produced different results"


@pytest.mark.skipif(not DATA_DIR.exists(), reason="Sample PDF directory not found")
def test_threaded_processing_thread_safety():
    """
    Test that multiple threads can process PDFs simultaneously without race conditions
    """
    pdf_files = list(DATA_DIR.rglob("*.pdf"))[:2]

    if not pdf_files:
        pytest.skip("No sample PDF files found for testing")

    results = {}
    errors = {}
    thread_ids = set()
    lock = threading.Lock()

    def process_with_thread_tracking(pdf_path: Path):
        """Process PDF while tracking thread ID and potential race conditions"""
        thread_id = threading.get_ident()

        with lock:
            thread_ids.add(thread_id)

        try:
            doc = _process_single_pdf(pdf_path, enable_ocr=False)

            with lock:
                results[pdf_path.name] = {
                    "thread_id": thread_id,
                    "pages": doc.num_pages,
                    "chars": doc.total_chars,
                    "source_format": doc.source_format,
                }
        except Exception as e:
            with lock:
                errors[pdf_path.name] = str(e)

    # Run with multiple threads
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_with_thread_tracking, pdf) for pdf in pdf_files
        ]

        # Wait for all to complete
        for future in as_completed(futures):
            future.result()  # This will raise if there was an exception

    # Verify no errors occurred
    assert not errors, f"Thread safety errors: {errors}"

    # Verify multiple threads were used (if we have multiple files)
    if len(pdf_files) > 1:
        assert len(thread_ids) > 1, "Multiple threads should have been used"

    # Verify all files were processed
    assert len(results) == len(pdf_files)

    # Verify results are reasonable
    for file_name, result in results.items():
        # Some PDFs might be empty or corrupted - just verify format is valid
        assert result["pages"] >= 0, f"Invalid page count in {file_name}"
        assert result["chars"] >= 0, f"Invalid character count in {file_name}"
        assert result["source_format"] in [
            "vector",
            "scan",
            "mixed",
        ], f"Invalid source format for {file_name}"

        # Log warning for empty documents but don't fail the test
        if result["pages"] == 0:
            print(
                f"Warning: {file_name} contains 0 pages - may be encrypted or corrupted"
            )


def test_pdf_processor_thread_local_state():
    """
    Test that PDFProcessor instances don't share state between threads
    This is a unit test that doesn't require sample data
    """
    results = {}
    lock = threading.Lock()

    def create_and_configure_processor(worker_id: int):
        """Each thread creates its own processor with different config"""
        processor = PDFProcessor(
            min_text_length=worker_id * 10,  # Different config per thread
            enable_ocr=worker_id % 2 == 0,  # Alternating OCR setting
        )

        config = {
            "min_text_length": processor.min_text_length,
            "enable_ocr": processor.enable_ocr,
            "thread_id": threading.get_ident(),
        }

        with lock:
            results[worker_id] = config

    # Create multiple threads with different configurations
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(create_and_configure_processor, i) for i in range(4)]

        for future in as_completed(futures):
            future.result()

    # Verify each thread had its own configuration
    assert len(results) == 4

    for worker_id, config in results.items():
        expected_min_length = worker_id * 10
        expected_ocr = worker_id % 2 == 0

        assert config["min_text_length"] == expected_min_length
        assert config["enable_ocr"] == expected_ocr


if __name__ == "__main__":
    # Allow running individual tests
    pytest.main([__file__, "-v"])
