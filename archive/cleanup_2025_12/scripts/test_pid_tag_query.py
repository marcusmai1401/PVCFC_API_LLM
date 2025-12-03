#!/usr/bin/env python
"""
Test script for P&ID tag location query
Query: "Tìm cho tôi thông tin vị trí của tag name 04 PV 5012 trong bản vẽ P&ID của cụm Ammonia"
Expected: Page 56/117 of "01. P&ID Ammonia Unit Rev12 (04000).pdf"
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

# API configuration
API_BASE_URL = "http://localhost:8000"
QUERY_ENDPOINT = f"{API_BASE_URL}/ask"

# Test configuration
TEST_QUERY = "Tìm cho tôi thông tin vị trí của tag name 04 PV 5012 trong bản vẽ P&ID của cụm Ammonia"
EXPECTED_DOCUMENT = "01. P&ID Ammonia Unit Rev12 (04000).pdf"
EXPECTED_PAGE = 56
TOTAL_PAGES = 117

logger.info("=" * 80)
logger.info("P&ID Tag Location Query Test")
logger.info("=" * 80)
logger.info(f"Query: {TEST_QUERY}")
logger.info(f"Expected: Page {EXPECTED_PAGE}/{TOTAL_PAGES} of '{EXPECTED_DOCUMENT}'")
logger.info("=" * 80)

# Check if API is running
try:
    response = requests.get(f"{API_BASE_URL}/healthz", timeout=5)
    if response.status_code != 200:
        logger.error(f"❌ API health check failed: {response.status_code}")
        sys.exit(1)
    logger.info(f"✅ API is running at {API_BASE_URL}")
except requests.exceptions.RequestException as e:
    logger.error(f"❌ Cannot connect to API at {API_BASE_URL}: {e}")
    logger.error("Please start the API server first:")
    logger.error("  python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000")
    sys.exit(1)

# Send query
logger.info("\nSending query to API...")
try:
    query_payload = {
        "query": TEST_QUERY,
        "query_type": "pid",  # Required: P&ID query type
        "hyde": True,
        "max_context": 8,
        "language": "vi",
    }

    response = requests.post(QUERY_ENDPOINT, json=query_payload, timeout=60)

    if response.status_code != 200:
        logger.error(f"❌ Query failed: {response.status_code}")
        logger.error(f"Response: {response.text}")
        sys.exit(1)

    result = response.json()

except requests.exceptions.RequestException as e:
    logger.error(f"❌ Query request failed: {e}")
    sys.exit(1)

# Analyze response
logger.info("\n" + "=" * 80)
logger.info("API Response Analysis")
logger.info("=" * 80)

answer = result.get("answer", "")
sources = result.get("sources", [])
query_type = result.get("query_type", "unknown")

logger.info(f"\n📝 Answer:\n{answer}\n")
logger.info(f"Query Type: {query_type}")
logger.info(f"Number of sources: {len(sources)}")

# Check if expected document and page are mentioned
found_document = False
found_page = False
found_in_sources = False
correct_source_index = -1

# Check answer text
if EXPECTED_DOCUMENT.lower() in answer.lower():
    found_document = True
    logger.info(f"✅ Document '{EXPECTED_DOCUMENT}' mentioned in answer")
else:
    logger.warning(f"⚠️  Document '{EXPECTED_DOCUMENT}' NOT mentioned in answer")

# Check for page number mentions
page_mentions = [
    f"page {EXPECTED_PAGE}",
    f"trang {EXPECTED_PAGE}",
    f"p. {EXPECTED_PAGE}",
    f"pg {EXPECTED_PAGE}",
    f"trang {EXPECTED_PAGE}/{TOTAL_PAGES}",
    f"page {EXPECTED_PAGE}/{TOTAL_PAGES}",
]

for mention in page_mentions:
    if mention.lower() in answer.lower():
        found_page = True
        logger.info(
            f"✅ Page {EXPECTED_PAGE} mentioned in answer (pattern: '{mention}')"
        )
        break

if not found_page:
    logger.warning(f"⚠️  Page {EXPECTED_PAGE} NOT explicitly mentioned in answer")

# Check sources
logger.info("\n📚 Sources:")
for idx, source in enumerate(sources, 1):
    doc_id = source.get("doc_id", "")
    file_path = source.get("file_path", "")
    page_num = source.get("page_num")
    chunk_id = source.get("chunk_id", "")
    score = source.get("score", 0.0)

    logger.info(f"\n  [{idx}] Score: {score:.4f}")
    logger.info(f"      Doc ID: {doc_id}")
    logger.info(f"      File: {file_path}")
    logger.info(f"      Page: {page_num}")
    logger.info(f"      Chunk: {chunk_id}")

    # Check if this is the expected source
    if EXPECTED_DOCUMENT in file_path and page_num == EXPECTED_PAGE:
        found_in_sources = True
        correct_source_index = idx
        logger.info(f"      ✅ THIS IS THE EXPECTED SOURCE!")

# Final verdict
logger.info("\n" + "=" * 80)
logger.info("Test Result")
logger.info("=" * 80)

test_passed = found_document and found_page and found_in_sources

if test_passed:
    logger.success(f"✅ TEST PASSED!")
    logger.success(f"   - Expected document mentioned: {found_document}")
    logger.success(f"   - Expected page mentioned: {found_page}")
    logger.success(
        f"   - Correct source in citations: {found_in_sources} (rank #{correct_source_index})"
    )
else:
    logger.error(f"❌ TEST FAILED!")
    logger.error(f"   - Expected document mentioned: {found_document}")
    logger.error(f"   - Expected page mentioned: {found_page}")
    logger.error(f"   - Correct source in citations: {found_in_sources}")

    if found_in_sources and correct_source_index > 1:
        logger.warning(
            f"   ⚠️  Correct source found but ranked #{correct_source_index} (not #1)"
        )

# Save detailed results
output_file = PROJECT_ROOT / "test_pid_tag_query_results.json"
test_result = {
    "timestamp": datetime.now().isoformat(),
    "query": TEST_QUERY,
    "expected": {
        "document": EXPECTED_DOCUMENT,
        "page": EXPECTED_PAGE,
        "total_pages": TOTAL_PAGES,
    },
    "test_result": {
        "passed": test_passed,
        "document_mentioned": found_document,
        "page_mentioned": found_page,
        "correct_source_in_citations": found_in_sources,
        "correct_source_rank": correct_source_index if found_in_sources else None,
    },
    "api_response": {"answer": answer, "query_type": query_type, "sources": sources},
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(test_result, f, indent=2, ensure_ascii=False)

logger.info(f"\n📄 Detailed results saved to: {output_file}")
logger.info("=" * 80)

sys.exit(0 if test_passed else 1)
