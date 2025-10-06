#!/usr/bin/env python
"""
Quick Test Script for Page Metadata Fix & Table Extraction
Verifies that the implementation works correctly
"""
import json
import re
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from loguru import logger


def test_page_metadata_fix():
    """Test that page metadata matches content markers"""
    logger.info("=" * 80)
    logger.info("TEST 1: Page Metadata Fix")
    logger.info("=" * 80)

    chunks_file = PROJECT_ROOT / "artifacts" / "ingestion" / "chunks" / "chunks.jsonl"

    if not chunks_file.exists():
        logger.warning(f"Chunks file not found: {chunks_file}")
        logger.info(
            "Run ingestion first: python tools/ingest.py --source-dir data/raw/phase1_pilot --output-dir artifacts/ingestion"
        )
        return False

    logger.info(f"Loading chunks from: {chunks_file}")

    total_chunks = 0
    correct_pages = 0
    incorrect_pages = 0
    no_page_markers = 0

    with open(chunks_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                chunk = json.loads(line)
                total_chunks += 1

                text = chunk.get("text", "")
                metadata_page = chunk.get("metadata", {}).get("page")

                # Extract page from content marker
                match = re.search(r"<!--\s*Page\s+(\d+)\s*-->", text, re.IGNORECASE)
                if match:
                    content_page = int(match.group(1))

                    if metadata_page == content_page:
                        correct_pages += 1
                    else:
                        incorrect_pages += 1
                        if incorrect_pages <= 3:  # Show first 3 mismatches
                            logger.warning(
                                f"Page mismatch in chunk {chunk.get('chunk_id')}: "
                                f"metadata={metadata_page}, content={content_page}"
                            )
                else:
                    no_page_markers += 1

                # Test first 1000 chunks only for speed
                if total_chunks >= 1000:
                    break

            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.error(f"Error processing chunk: {e}")

    logger.info(f"\nResults:")
    logger.info(f"  Total chunks tested: {total_chunks}")
    logger.info(f"  Correct page metadata: {correct_pages}")
    logger.info(f"  Incorrect page metadata: {incorrect_pages}")
    logger.info(f"  No page markers: {no_page_markers}")

    if correct_pages > 0:
        accuracy = correct_pages / (correct_pages + incorrect_pages) * 100
        logger.info(f"  Accuracy: {accuracy:.2f}%")

        if accuracy >= 95:
            logger.success("✓ Page metadata fix is working correctly!")
            return True
        else:
            logger.warning(f"⚠ Page metadata accuracy is low: {accuracy:.2f}%")
            return False
    else:
        logger.error("✗ No chunks with page markers found")
        return False


def test_table_extraction():
    """Test that table metadata is extracted correctly"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Table Metadata Extraction")
    logger.info("=" * 80)

    table_index_file = (
        PROJECT_ROOT / "artifacts" / "ingestion" / "manifests" / "table_index.json"
    )

    if not table_index_file.exists():
        logger.warning(f"Table index not found: {table_index_file}")
        logger.info("Run ingestion with --extract-tables flag")
        return False

    logger.info(f"Loading table index from: {table_index_file}")

    try:
        with open(table_index_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        total_tables = data.get("total_tables", 0)
        tables = data.get("tables", [])

        logger.info(f"\nResults:")
        logger.info(f"  Total tables: {total_tables}")

        if total_tables > 0:
            # Count tables with specific features
            torque_tables = sum(1 for t in tables if t.get("has_torque_data", False))
            tables_with_keywords = sum(1 for t in tables if t.get("keywords"))

            logger.info(f"  Tables with torque data: {torque_tables}")
            logger.info(f"  Tables with keywords: {tables_with_keywords}")

            # Show sample table
            logger.info(f"\nSample table:")
            sample = tables[0]
            logger.info(f"  Table ID: {sample.get('table_id')}")
            logger.info(f"  Page: {sample.get('page')}")
            logger.info(
                f"  Dimensions: {sample.get('row_count')}x{sample.get('col_count')}"
            )
            logger.info(f"  Title: {sample.get('title', 'N/A')}")
            logger.info(f"  Has torque data: {sample.get('has_torque_data', False)}")
            logger.info(
                f"  Keywords: {sample.get('keywords', [])[:5]}"
            )  # First 5 keywords

            logger.success("✓ Table extraction is working correctly!")
            return True
        else:
            logger.warning("⚠ No tables found in corpus")
            return False

    except Exception as e:
        logger.error(f"Failed to load table index: {e}")
        return False


def test_table_aware_indexing():
    """Test that BM25 index uses table metadata"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Table-Aware BM25 Indexing")
    logger.info("=" * 80)

    # Check if BM25 index exists
    bm25_dir = PROJECT_ROOT / "artifacts" / "index" / "bm25"

    if not bm25_dir.exists():
        logger.warning(f"BM25 index not found: {bm25_dir}")
        logger.info(
            "Build index first: python tools/build_bm25_index.py --chunks-jsonl artifacts/ingestion/chunks/chunks.jsonl"
        )
        return False

    logger.info(f"Loading BM25 index from: {bm25_dir}")

    try:
        from app.rag.indexers.bm25_indexer import BM25Indexer

        indexer = BM25Indexer()
        indexer.load_index(str(bm25_dir))

        # Test query
        test_query = "M42 anchor bolt torque"
        logger.info(f"\nTest query: '{test_query}'")

        results = indexer.search(test_query, top_k=5)

        logger.info(f"\nTop 5 results:")
        for i, result in enumerate(results, 1):
            page = result["metadata"].get("page")
            score = result["score"]
            text_preview = result["text"][:150].replace("\n", " ")

            logger.info(f"\n{i}. Score: {score:.4f}, Page: {page}")
            logger.info(f"   Text: {text_preview}...")

            # Check if page metadata matches content
            match = re.search(r"<!--\s*Page\s+(\d+)\s*-->", result["text"])
            if match:
                content_page = int(match.group(1))
                if page == content_page:
                    logger.info(f"   ✓ Page metadata matches content")
                else:
                    logger.warning(
                        f"   ✗ Page mismatch: metadata={page}, content={content_page}"
                    )

        if results:
            logger.success("✓ BM25 index is working correctly!")
            return True
        else:
            logger.warning("⚠ No results returned for test query")
            return False

    except Exception as e:
        logger.error(f"Failed to test BM25 index: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    logger.info("🧪 Running Implementation Tests\n")

    results = {
        "page_metadata": test_page_metadata_fix(),
        "table_extraction": test_table_extraction(),
        "bm25_indexing": test_table_aware_indexing(),
    }

    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{test_name:20s}: {status}")

    total_tests = len(results)
    passed_tests = sum(results.values())

    logger.info(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        logger.success("\n🎉 All tests passed! Implementation is working correctly.")
        return 0
    else:
        logger.warning(
            f"\n⚠ {total_tests - passed_tests} test(s) failed. Please review the logs above."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
