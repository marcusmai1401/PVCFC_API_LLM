#!/usr/bin/env python
"""
P&ID Accuracy Audit Script
===========================
Tests the P&ID pipeline end-to-end against ground truth from test_pid.md

Target Accuracy: 4/5 (ideally 5/5)
Query 5 can tolerate minor variance, others must be exact.
"""

import argparse
import csv
import json
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from loguru import logger

# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_OS_BASE = "http://localhost:9200"
DEFAULT_TEST_MD = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\test_pid.md"
LOG_DIR_BASE = Path("logs/pid_audit")

ENDPOINT_CANDIDATES = [
    "/ask",
    "/query",
    "/api/ask",
    "/api/query",
    "/v1/query",
    "/rag/query",
]

# ============================================================================
# HELPERS
# ============================================================================


def check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def wait_for_api(base_url: str, timeout: int = 60) -> bool:
    """Wait for API to become ready"""
    logger.info(f"Waiting for API at {base_url} (timeout: {timeout}s)")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Try health endpoint first
            for endpoint in ["/health", "/healthz", "/"]:
                try:
                    response = requests.get(f"{base_url}{endpoint}", timeout=2)
                    if response.status_code < 500:
                        logger.success(f"API is ready at {base_url}")
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        time.sleep(2)

    logger.error("API did not become ready in time")
    return False


def discover_endpoint(base_url: str) -> Optional[str]:
    """Discover the query endpoint from OpenAPI spec or by probing"""
    logger.info("Discovering query endpoint...")

    # Try OpenAPI first
    try:
        response = requests.get(f"{base_url}/openapi.json", timeout=5)
        if response.status_code == 200:
            spec = response.json()
            paths = spec.get("paths", {})

            # Look for paths with "query" in body schema
            for path, methods in paths.items():
                for method, details in methods.items():
                    if method.lower() != "post":
                        continue

                    # Check request body schema
                    request_body = details.get("requestBody", {})
                    content = request_body.get("content", {})
                    json_schema = content.get("application/json", {})
                    schema = json_schema.get("schema", {})
                    properties = schema.get("properties", {})

                    if "query" in properties and "query_type" in properties:
                        logger.success(f"Found endpoint: POST {path}")
                        return path
    except Exception as e:
        logger.warning(f"Failed to read OpenAPI spec: {e}")

    # Fallback: probe candidates
    for candidate in ENDPOINT_CANDIDATES:
        try:
            test_payload = {"query": "test"}
            response = requests.post(
                f"{base_url}{candidate}", json=test_payload, timeout=5
            )
            if response.status_code in [200, 400, 422]:  # 400/422 means endpoint exists
                logger.success(f"Found endpoint via probe: POST {candidate}")
                return candidate
        except Exception:
            continue

    logger.error("Could not discover query endpoint")
    return None


def parse_ground_truth(test_md_path: Path) -> List[Dict[str, Any]]:
    """Parse ground truth from test_pid.md"""
    logger.info(f"Parsing ground truth from {test_md_path}")

    content = test_md_path.read_text(encoding="utf-8")

    # Pattern: Query N: <query text>\nĐáp án: Trang X/117
    pattern = r"Query\s+(\d+):\s*(.+?)\s*\n\s*Đáp án:\s*(?:Trang\s+)?(\d+)(?:/117)?"
    matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)

    ground_truth = []
    for query_num, query_text, page_str in matches:
        ground_truth.append(
            {
                "query_id": int(query_num),
                "query": query_text.strip(),
                "expected_page": int(page_str),
            }
        )

    logger.info(f"Parsed {len(ground_truth)} ground truth queries")
    for gt in ground_truth:
        logger.debug(
            f"  Q{gt['query_id']}: '{gt['query'][:50]}...' → Page {gt['expected_page']}"
        )

    return ground_truth


def extract_pages_from_response(response_json: Dict) -> List[int]:
    """Extract page numbers from API response (robust to multiple formats)"""
    pages = set()

    # Try multiple possible locations
    locations = [
        ("citations", "page"),
        ("citations", "page_number"),
        ("results", "page"),
        ("sources", "page"),
        ("chunks", "page"),
        ("meta", "pages"),
    ]

    for location_path, page_field in locations:
        try:
            if location_path in response_json:
                items = response_json[location_path]
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and page_field in item:
                            page = item[page_field]
                            if isinstance(page, int):
                                pages.add(page)
        except Exception:
            continue

    # Also try nested paths
    try:
        if "results" in response_json:
            for result in response_json["results"]:
                if "contexts" in result:
                    for ctx in result["contexts"]:
                        if "metadata" in ctx and "page" in ctx["metadata"]:
                            pages.add(ctx["metadata"]["page"])
    except Exception:
        pass

    return sorted(list(pages))


def query_api(
    base_url: str,
    endpoint: str,
    query: str,
    query_type: str = "pid",
    top_k: int = 10,
) -> Tuple[Optional[Dict], Optional[str]]:
    """Send query to API and return response"""
    url = f"{base_url}{endpoint}"

    payload = {
        "query": query,
        "query_type": query_type,
        "max_context": top_k,
        "language": "vi",
    }

    try:
        logger.info(f"Querying API: {query[:80]}...")
        response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 200:
            return response.json(), None
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.error(error_msg)
            return None, error_msg
    except Exception as e:
        error_msg = f"Request failed: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


def query_opensearch(
    os_base: str,
    index: str,
    query_body: Dict,
) -> Tuple[Optional[Dict], Optional[str]]:
    """Query OpenSearch directly"""
    url = f"{os_base}/{index}/_search"

    try:
        response = requests.post(url, json=query_body, timeout=10)
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"HTTP {response.status_code}"
    except Exception as e:
        return None, str(e)


# ============================================================================
# LAYER CHECKS
# ============================================================================


def check_layer_1_data(os_base: str, log_dir: Path, ground_truth: List[Dict]) -> Dict:
    """Layer 1: Validate data in pvcfc_pid_tags index"""
    logger.info("=" * 80)
    logger.info("LAYER 1: Data Validation (pvcfc_pid_tags)")
    logger.info("=" * 80)

    results = {
        "indices_exist": False,
        "tag_searches": [],
        "summary": "",
    }

    # Check indices
    try:
        response = requests.get(f"{os_base}/_cat/indices?v", timeout=5)
        if response.status_code == 200:
            indices_text = response.text
            results["indices_exist"] = "pvcfc_pid_tags" in indices_text
            (log_dir / "os_indices.txt").write_text(indices_text, encoding="utf-8")
            logger.info(
                f"Indices check: pvcfc_pid_tags exists = {results['indices_exist']}"
            )
    except Exception as e:
        logger.error(f"Failed to check indices: {e}")

    if not results["indices_exist"]:
        results["summary"] = "CRITICAL: pvcfc_pid_tags index not found"
        return results

    # Get mapping
    try:
        response = requests.get(f"{os_base}/pvcfc_pid_tags/_mapping", timeout=5)
        if response.status_code == 200:
            mapping = response.json()
            (log_dir / "os_mapping_pvcfc_pid_tags.json").write_text(
                json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8"
            )
    except Exception as e:
        logger.warning(f"Failed to get mapping: {e}")

    # Search for each tag
    for gt in ground_truth:
        # Extract tag from query (pattern: "04 PSV 3926")
        tag_match = re.search(r"(\d{2}\s+[A-Z]{2,5}\s+\d{3,5})", gt["query"])
        if not tag_match:
            logger.warning(f"Could not extract tag from query: {gt['query']}")
            continue

        tag = tag_match.group(1)
        logger.info(f"Searching for tag: '{tag}' (expected page {gt['expected_page']})")

        # Try exact term search on tag.keyword
        search_body = {"size": 5, "query": {"term": {"tag.keyword": tag}}}

        response, error = query_opensearch(os_base, "pvcfc_pid_tags", search_body)

        tag_result = {
            "query_id": gt["query_id"],
            "tag": tag,
            "expected_page": gt["expected_page"],
            "found": False,
            "pages_in_index": [],
            "search_error": error,
        }

        if response:
            hits = response.get("hits", {}).get("hits", [])
            if hits:
                tag_result["found"] = True
                for hit in hits:
                    source = hit["_source"]
                    page = source.get("page")
                    if page:
                        tag_result["pages_in_index"].append(page)

                logger.success(
                    f"  Found tag in index, pages: {tag_result['pages_in_index']}"
                )

                # Check if expected page is in results
                if gt["expected_page"] in tag_result["pages_in_index"]:
                    logger.success(f"  ✓ Expected page {gt['expected_page']} FOUND")
                else:
                    logger.error(f"  ✗ Expected page {gt['expected_page']} NOT FOUND")
            else:
                logger.warning(f"  Tag not found with exact term search")

        results["tag_searches"].append(tag_result)

    # Summary
    found_count = sum(1 for r in results["tag_searches"] if r["found"])
    page_match_count = sum(
        1 for r in results["tag_searches"] if r["expected_page"] in r["pages_in_index"]
    )

    results["summary"] = (
        f"Tags found: {found_count}/{len(ground_truth)} | "
        f"Expected pages matched: {page_match_count}/{len(ground_truth)}"
    )

    logger.info(f"Layer 1 Summary: {results['summary']}")

    return results


def check_layer_2_api(
    api_base: str,
    endpoint: str,
    log_dir: Path,
    ground_truth: List[Dict],
) -> Dict:
    """Layer 2: Test API queries"""
    logger.info("=" * 80)
    logger.info("LAYER 2: API Query Testing")
    logger.info("=" * 80)

    results = {
        "queries": [],
        "accuracy": 0.0,
        "summary": "",
    }

    for gt in ground_truth:
        logger.info(f"Query {gt['query_id']}: {gt['query'][:80]}...")

        response_json, error = query_api(
            api_base,
            endpoint,
            gt["query"],
            query_type="pid",
            top_k=10,
        )

        query_result = {
            "query_id": gt["query_id"],
            "query": gt["query"],
            "expected_page": gt["expected_page"],
            "response_ok": response_json is not None,
            "error": error,
            "pages_returned": [],
            "pass": False,
        }

        if response_json:
            # Save response
            response_file = log_dir / f"api_response_q{gt['query_id']}.json"
            response_file.write_text(
                json.dumps(response_json, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Extract pages
            pages = extract_pages_from_response(response_json)
            query_result["pages_returned"] = pages

            # Check if expected page is in results
            # For query 5, allow ±1 tolerance
            tolerance = 1 if gt["query_id"] == 5 else 0

            for page in pages:
                if abs(page - gt["expected_page"]) <= tolerance:
                    query_result["pass"] = True
                    break

            if query_result["pass"]:
                logger.success(
                    f"  ✓ PASS - Expected page {gt['expected_page']} found in {pages}"
                )
            else:
                logger.error(
                    f"  ✗ FAIL - Expected page {gt['expected_page']} not in {pages}"
                )
        else:
            logger.error(f"  ✗ FAIL - API error: {error}")

        results["queries"].append(query_result)

    # Calculate accuracy
    pass_count = sum(1 for q in results["queries"] if q["pass"])
    total = len(results["queries"])
    results["accuracy"] = pass_count / total if total > 0 else 0.0

    results["summary"] = f"Accuracy: {pass_count}/{total} ({results['accuracy']:.1%})"
    logger.info(f"Layer 2 Summary: {results['summary']}")

    return results


# ============================================================================
# MAIN AUDIT
# ============================================================================


def run_audit(args):
    """Run complete audit"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = LOG_DIR_BASE / timestamp
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(log_dir / "audit.log", level="DEBUG")
    logger.info("=" * 80)
    logger.info("P&ID ACCURACY AUDIT")
    logger.info("=" * 80)
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Log directory: {log_dir}")
    logger.info(f"API: {args.api}")
    logger.info(f"OpenSearch: {args.opensearch}")
    logger.info(f"Ground truth: {args.ground_truth}")

    # Parse ground truth
    test_md_path = Path(args.ground_truth)
    if not test_md_path.exists():
        logger.error(f"Ground truth file not found: {test_md_path}")
        return 1

    ground_truth = parse_ground_truth(test_md_path)
    if not ground_truth:
        logger.error("No ground truth queries found")
        return 1

    # Check API availability
    api_host, api_port = args.api.replace("http://", "").split(":")
    if not check_port(api_host, int(api_port)):
        logger.warning("API not responding, waiting...")
        if not wait_for_api(args.api):
            logger.error("API is not available")
            return 1

    # Discover endpoint
    endpoint = discover_endpoint(args.api)
    if not endpoint:
        logger.error("Could not discover query endpoint")
        return 1

    # Run layer checks
    layer1_results = check_layer_1_data(args.opensearch, log_dir, ground_truth)
    layer2_results = check_layer_2_api(args.api, endpoint, log_dir, ground_truth)

    # Generate report
    generate_report(log_dir, ground_truth, layer1_results, layer2_results, endpoint)

    # Summary
    logger.info("=" * 80)
    logger.info("AUDIT COMPLETE")
    logger.info("=" * 80)
    logger.info(
        f"Accuracy: {layer2_results['accuracy']:.1%} (target: 80% minimum, 100% ideal)"
    )
    logger.info(f"Results saved to: {log_dir}")

    if layer2_results["accuracy"] >= 0.8:
        logger.success("✓ Audit PASSED (≥80% accuracy)")
        return 0
    else:
        logger.error("✗ Audit FAILED (<80% accuracy)")
        return 1


def generate_report(
    log_dir: Path,
    ground_truth: List[Dict],
    layer1: Dict,
    layer2: Dict,
    endpoint: str = "/ask",
):
    """Generate comprehensive audit report"""
    report_path = log_dir / "report.md"
    csv_path = log_dir / "summary.csv"

    # CSV summary
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Query ID", "Query", "Expected Page", "Pages Returned", "Pass"]
        )

        for q in layer2["queries"]:
            writer.writerow(
                [
                    q["query_id"],
                    q["query"],
                    q["expected_page"],
                    ", ".join(map(str, q["pages_returned"]))
                    if q["pages_returned"]
                    else "N/A",
                    "PASS" if q["pass"] else "FAIL",
                ]
            )

    # Markdown report
    report = f"""# P&ID Accuracy Audit Report

**Timestamp:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Log Directory:** `{log_dir}`

---

## Executive Summary

**Overall Accuracy:** {layer2['accuracy']:.1%} ({sum(1 for q in layer2['queries'] if q['pass'])}/{len(layer2['queries'])} queries passed)

**Target:** ≥80% (4/5 queries), ideally 100% (5/5 queries)

**Status:** {'✅ PASSED' if layer2['accuracy'] >= 0.8 else '❌ FAILED'}

---

## Test Results

| Query | Expected Page | Pages Returned | Result |
|-------|--------------|----------------|--------|
"""

    for q in layer2["queries"]:
        pages_str = (
            ", ".join(map(str, q["pages_returned"])) if q["pages_returned"] else "N/A"
        )
        status = "✅ PASS" if q["pass"] else "❌ FAIL"
        report += f"| Q{q['query_id']}: {q['query'][:50]}... | {q['expected_page']} | {pages_str} | {status} |\n"

    report += f"""

---

## Layer 1: Data Validation (pvcfc_pid_tags)

**Summary:** {layer1['summary']}

**Indices Exist:** {'✅ Yes' if layer1['indices_exist'] else '❌ No'}

### Tag Search Results

| Tag | Expected Page | Found in Index | Pages in Index |
|-----|--------------|----------------|----------------|
"""

    for t in layer1["tag_searches"]:
        found = "✅ Yes" if t["found"] else "❌ No"
        pages_str = (
            ", ".join(map(str, t["pages_in_index"])) if t["pages_in_index"] else "N/A"
        )
        report += f"| {t['tag']} | {t['expected_page']} | {found} | {pages_str} |\n"

    report += f"""

---

## Layer 2: API Query Testing

**Summary:** {layer2['summary']}

**Endpoint:** `POST {endpoint}` (discovered automatically)

### Detailed Results

"""

    for q in layer2["queries"]:
        report += f"""#### Query {q['query_id']}: {q['query']}

- **Expected Page:** {q['expected_page']}
- **Pages Returned:** {', '.join(map(str, q['pages_returned'])) if q['pages_returned'] else 'N/A'}
- **Result:** {'✅ PASS' if q['pass'] else '❌ FAIL'}
- **Response File:** `api_response_q{q['query_id']}.json`

"""

    report += """

---

## Root Cause Analysis

"""

    # Analyze failures
    failed_queries = [q for q in layer2["queries"] if not q["pass"]]

    if not failed_queries:
        report += "**No failures detected.** All queries returned correct pages.\n"
    else:
        report += "### Failed Queries:\n\n"
        for q in failed_queries:
            report += f"**Query {q['query_id']}:** {q['query']}\n\n"

            # Find corresponding Layer 1 result
            tag_match = re.search(r"(\d{2}\s+[A-Z]{2,5}\s+\d{3,5})", q["query"])
            if tag_match:
                tag = tag_match.group(1)
                layer1_result = next(
                    (t for t in layer1["tag_searches"] if t["tag"] == tag), None
                )

                if layer1_result:
                    if not layer1_result["found"]:
                        report += f"- **Issue:** Tag `{tag}` not found in `pvcfc_pid_tags` index\n"
                        report += f"- **Layer:** Data/Indexing (Layer 1)\n"
                        report += f"- **Fix:** Re-index P&ID document or check tag extraction logic\n\n"
                    elif q["expected_page"] not in layer1_result["pages_in_index"]:
                        report += f"- **Issue:** Tag `{tag}` found but expected page {q['expected_page']} missing\n"
                        report += f"- **Layer:** Data/Indexing (Layer 1)\n"
                        report += f"- **Fix:** Verify tag extraction for page {q['expected_page']}\n\n"
                    else:
                        report += f"- **Issue:** Tag found with correct page in index, but API returned wrong pages\n"
                        report += f"- **Layer:** Retrieval/Routing (Layer 2)\n"
                        report += f"- **Fix:** Check query routing, RRF fusion weights, or response builder\n\n"

    report += """

---

## Recommended Actions

### High Priority

1. **Verify pvcfc_pid_tags index:** Ensure all tags are extracted and indexed correctly
2. **Check query routing:** Confirm `query_type="pid"` reaches the correct retriever
3. **Validate tag search:** Ensure exact term search on `tag.keyword` field works

### Medium Priority

1. **RRF fusion weights:** Prioritize exact tag matches over semantic search
2. **Page number mapping:** Verify 0-based vs 1-based indexing consistency
3. **Response builder:** Ensure correct page field is surfaced in citations

### Low Priority

1. **Add debug mode:** Include intermediate hits and scores in API response
2. **CI integration:** Add this audit script to CI pipeline

---

## Files Generated

- `report.md` - This report
- `summary.csv` - Test results in CSV format
- `audit.log` - Detailed execution log
- `api_response_qN.json` - API responses for each query
- `os_indices.txt` - OpenSearch indices list
- `os_mapping_pvcfc_pid_tags.json` - Index mapping

---

**End of Report**
"""

    report_path.write_text(report, encoding="utf-8")
    logger.success(f"Report generated: {report_path}")


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="P&ID Accuracy Audit")
    parser.add_argument(
        "--api",
        default=DEFAULT_API_BASE,
        help=f"API base URL (default: {DEFAULT_API_BASE})",
    )
    parser.add_argument(
        "--opensearch",
        default=DEFAULT_OS_BASE,
        help=f"OpenSearch base URL (default: {DEFAULT_OS_BASE})",
    )
    parser.add_argument(
        "--ground-truth",
        default=DEFAULT_TEST_MD,
        help=f"Ground truth file (default: {DEFAULT_TEST_MD})",
    )

    args = parser.parse_args()

    try:
        sys.exit(run_audit(args))
    except KeyboardInterrupt:
        logger.warning("Audit interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Audit failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
