"""
P1: Chunking Integration Test

Tests all chunking strategies: text, deduplication, and P&ID schema.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.ingestion.chunkers.text_chunker import TextChunker
from app.ingestion.dedup import ContentDeduplicator
from app.ingestion.domain.pid_schema import (
    extract_tags_from_text,
    get_synonyms,
    normalize_tag,
    normalize_unit,
    parse_equipment_tag,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_text_chunker():
    """Test text chunker with sample technical text"""
    logger.info("=" * 70)
    logger.info("TEST 1: TEXT CHUNKER")
    logger.info("=" * 70)

    # Sample technical text
    sample_text = """
    # CO2 Compressor System Specification

    The CO2 compressor system (E-404) consists of a two-stage centrifugal compressor
    with intercooling. The first stage operates at 5,000 RPM delivering 1200 SCFM at
    50 PSI discharge pressure. The second stage operates at 8,000 RPM delivering 1200
    SCFM at 150 PSI discharge pressure.

    ## Lube Oil System

    The lube oil system (P-101) includes a centrifugal pump with capacity 500 gallons,
    circulation rate 100 GPM, filtration 5 micron absolute, operating temperature
    120-140°F maintained by heat exchanger (HX-202) with automatic temperature control
    valve (V-303). System includes duplex filters with differential pressure indicators
    and low pressure alarm at 15 PSI.

    ## Safety Features

    The system includes anti-surge control, vibration monitoring, and automatic
    shutdown on high temperature. Emergency shutdown is triggered at 180°F.
    """

    # Initialize chunker
    chunker = TextChunker(
        chunk_size=300,  # Smaller for testing
        chunk_overlap=50,
        preserve_headers=True,
        extract_tags=True,
    )

    # Chunk the text
    chunks = chunker.chunk(
        text=sample_text, doc_id="test_doc_001", page=1, metadata={"source": "test"}
    )

    # Verify results
    logger.info(f"\n✓ Created {len(chunks)} chunks")

    for i, chunk in enumerate(chunks, 1):
        logger.info(f"\nChunk {i}:")
        logger.info(f"  ID: {chunk.chunk_id}")
        logger.info(f"  Tokens: {chunk.token_count}")
        logger.info(f"  Chars: {chunk.char_count}")
        logger.info(f"  Text preview: {chunk.text[:80]}...")

        if "headers" in chunk.metadata:
            logger.info(f"  Headers: {chunk.metadata['headers']}")

        if "equipment_tags" in chunk.metadata:
            logger.info(f"  Equipment tags: {chunk.metadata['equipment_tags']}")

    # Get metrics
    metrics = chunker.get_metrics()
    logger.info(f"\nChunker Metrics:")
    logger.info(f"  Chunks created: {metrics['chunks_created']}")
    logger.info(f"  Total tokens: {metrics['total_tokens_processed']}")
    logger.info(
        f"  Avg tokens/chunk: {metrics['total_tokens_processed'] // max(1, metrics['chunks_created'])}"
    )

    assert len(chunks) >= 1, "Should create at least one chunk"
    assert all(
        chunk.token_count > 0 for chunk in chunks
    ), "All chunks should have tokens"

    logger.info("\n✓ Text chunker test PASSED")
    return True


def test_deduplication():
    """Test content deduplication"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: CONTENT DEDUPLICATION")
    logger.info("=" * 70)

    # Initialize deduplicator
    dedup = ContentDeduplicator()

    # Sample texts (some duplicates)
    texts = [
        "The pump P-101 operates at 3560 RPM.",
        "Heat exchanger HX-202 has a capacity of 1000 BTU/hr.",
        "The pump P-101 operates at 3560 RPM.",  # Duplicate
        "Valve V-303 is a control valve for pressure regulation.",
        "THE PUMP P-101 OPERATES AT 3560 RPM.",  # Duplicate (case insensitive)
        "Compressor E-404 delivers 1200 SCFM.",
        "  The pump P-101 operates at 3560 RPM.  ",  # Duplicate (whitespace)
    ]

    # Check for duplicates
    unique_count = 0
    duplicate_count = 0

    for i, text in enumerate(texts, 1):
        is_dup = dedup.is_duplicate(text)
        status = "DUPLICATE" if is_dup else "UNIQUE"
        logger.info(f"Text {i}: {status} - '{text[:50]}...'")

        if is_dup:
            duplicate_count += 1
        else:
            unique_count += 1

    # Get metrics
    metrics = dedup.get_metrics()
    logger.info(f"\nDeduplication Metrics:")
    logger.info(f"  Total checked: {metrics['total_checked']}")
    logger.info(f"  Duplicates found: {metrics['duplicates_found']}")
    logger.info(f"  Unique content: {metrics['unique_content']}")
    logger.info(f"  Duplicate rate: {metrics['duplicate_rate']:.1%}")

    assert unique_count == 4, f"Should have 4 unique texts, got {unique_count}"
    assert duplicate_count == 3, f"Should have 3 duplicates, got {duplicate_count}"
    assert metrics["duplicate_rate"] > 0.4, "Should have >40% duplicate rate"

    logger.info("\n✓ Deduplication test PASSED")
    return True


def test_pid_schema():
    """Test P&ID domain schema"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: P&ID DOMAIN SCHEMA")
    logger.info("=" * 70)

    # Test tag normalization
    logger.info("\nTag Normalization:")
    test_tags = ["P101", "P-101", "ABC-P-101", "HX202A", "FI-301"]

    for tag in test_tags:
        normalized = normalize_tag(tag)
        logger.info(f"  {tag:15} → {normalized}")

    # Test tag parsing
    logger.info("\nTag Parsing:")
    for tag in ["P-101", "HX-202A", "FI-301", "E-404"]:
        parsed = parse_equipment_tag(tag)
        if parsed:
            logger.info(
                f"  {tag}: {parsed.equipment_type.value} (prefix={parsed.prefix}, num={parsed.number})"
            )

    # Test tag extraction from text
    logger.info("\nTag Extraction from Text:")
    text = "The system includes pump P-101, heat exchanger HX-202, and valve V-303 for pressure control."
    tags = extract_tags_from_text(text)
    logger.info(f"  Text: {text}")
    logger.info(f"  Extracted tags: {[t.normalized_tag for t in tags]}")

    # Test unit normalization
    logger.info("\nUnit Normalization:")
    test_texts = [
        "150 psi discharge pressure",
        "250 gpm flow rate",
        "3560 rpm motor speed",
        "Operating at 140 f",
    ]

    for text in test_texts:
        normalized = normalize_unit(text)
        logger.info(f"  {text:30} → {normalized}")

    # Test synonyms
    logger.info("\nSynonyms:")
    test_terms = ["pump", "bơm", "heat exchanger"]

    for term in test_terms:
        synonyms = get_synonyms(term)
        logger.info(f"  {term}: {synonyms[:3]}")  # Show first 3

    assert len(tags) == 3, "Should extract 3 tags"
    assert all(t.normalized_tag for t in tags), "All tags should have normalized form"

    logger.info("\n✓ P&ID schema test PASSED")
    return True


def test_mixed_language():
    """Test mixed Vietnamese/English text"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: MIXED LANGUAGE SUPPORT")
    logger.info("=" * 70)

    # Vietnamese + English mixed text
    mixed_text = """
    Bơm ly tâm P-101 operates at 3560 RPM with flow rate 250 GPM.
    Thiết bị trao đổi nhiệt HX-202 maintains temperature at 140°F.
    Van điều khiển V-303 regulates áp suất from 50 PSI to 150 PSI.
    """

    # Chunk it
    chunker = TextChunker(chunk_size=200, chunk_overlap=40, min_chunk_size=10)
    chunks = chunker.chunk(mixed_text, doc_id="mixed_001")

    logger.info(f"\nMixed text chunked into {len(chunks)} chunks")

    for i, chunk in enumerate(chunks, 1):
        logger.info(f"\nChunk {i}:")
        logger.info(f"  Text: {chunk.text}")
        logger.info(f"  Tokens: {chunk.token_count}")

    # Verify both languages preserved
    combined_text = " ".join(c.text for c in chunks)
    assert (
        "Bơm" in combined_text or "bơm" in combined_text.lower()
    ), "Vietnamese should be preserved"
    assert "operates" in combined_text.lower(), "English should be preserved"

    logger.info("\n✓ Mixed language test PASSED")
    return True


def run_integration_test():
    """Run complete P1 integration test"""
    logger.info("\n" + "=" * 80)
    logger.info("P1: CHUNKING & DOMAIN NORMALIZATION - INTEGRATION TEST")
    logger.info("=" * 80)

    results = {
        "text_chunker": False,
        "deduplication": False,
        "pid_schema": False,
        "mixed_language": False,
    }

    try:
        results["text_chunker"] = test_text_chunker()
    except Exception as e:
        logger.error(f"Text chunker test failed: {e}")
        logger.exception(e)

    try:
        results["deduplication"] = test_deduplication()
    except Exception as e:
        logger.error(f"Deduplication test failed: {e}")
        logger.exception(e)

    try:
        results["pid_schema"] = test_pid_schema()
    except Exception as e:
        logger.error(f"P&ID schema test failed: {e}")
        logger.exception(e)

    try:
        results["mixed_language"] = test_mixed_language()
    except Exception as e:
        logger.error(f"Mixed language test failed: {e}")
        logger.exception(e)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{test_name:20}: {status}")

    all_passed = all(results.values())

    logger.info("\n" + "-" * 80)
    if all_passed:
        logger.info("✓✓✓ ALL TESTS PASSED ✓✓✓")
        logger.info("\nP1 (Chunking & Domain Normalization) is COMPLETE and VALIDATED")
        logger.info("System ready for:")
        logger.info("  - Task-aware text chunking with headers")
        logger.info("  - Content deduplication")
        logger.info("  - P&ID tag extraction and normalization")
        logger.info("  - Mixed language support (VI/EN)")
    else:
        logger.error("✗✗✗ SOME TESTS FAILED ✗✗✗")

    logger.info("=" * 80)

    return all_passed


def main():
    """Main entry point"""
    success = run_integration_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
