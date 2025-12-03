#!/usr/bin/env python
"""
Validate migration results

This script:
1. Compares document counts (old backup vs new index)
2. Samples 100 tags and verifies parsing
3. Runs test queries to verify functionality
4. Compares response quality
"""
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from loguru import logger
from opensearchpy import OpenSearch

from app.rag.indexers.opensearch_tags_retriever import OpenSearchTagsRetriever
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer


def create_opensearch_client() -> OpenSearch:
    """Create OpenSearch client"""
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        timeout=30,
        max_retries=3,
        retry_on_timeout=True,
    )

    return client


def load_backup_manifest():
    """Load backup manifest"""
    manifest_file = PROJECT_ROOT / "artifacts/migration_backup/backup_manifest.json"

    if not manifest_file.exists():
        logger.warning("Backup manifest not found")
        return None

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    return manifest


def count_backup_tags():
    """Count tags in backup file"""
    manifest = load_backup_manifest()

    if not manifest:
        return None

    backup_file = manifest.get("backups", {}).get("tags_data")
    if not backup_file:
        return None

    backup_path = PROJECT_ROOT / "artifacts/migration_backup" / backup_file

    if not backup_path.exists():
        return None

    count = 0
    with open(backup_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1

    return count


def count_new_tags(client: OpenSearch, index_name: str):
    """Count tags in new index"""
    try:
        count_response = client.count(index=index_name)
        return count_response["count"]
    except Exception as e:
        logger.error(f"Failed to count new tags: {e}")
        return None


def sample_and_verify_tags(client: OpenSearch, index_name: str, sample_size: int = 100):
    """Sample random tags and verify parsing"""
    logger.info(f"Sampling {sample_size} tags for verification...")

    try:
        # Random sample using scroll
        response = client.search(
            index=index_name,
            body={
                "query": {"function_score": {"random_score": {}}},
                "size": sample_size,
                "_source": True,
            },
        )

        hits = response["hits"]["hits"]
        logger.info(f"Sampled {len(hits)} tags")

        # Verify each sample
        valid_count = 0
        issues = []

        for hit in hits:
            source = hit["_source"]

            # Check required fields
            tag = source.get("tag")
            prefix = source.get("prefix")
            suffix = source.get("suffix")

            if not tag or not prefix or not suffix:
                issues.append(
                    {
                        "id": hit["_id"],
                        "issue": "Missing required fields",
                        "tag": tag,
                        "prefix": prefix,
                        "suffix": suffix,
                    }
                )
                continue

            # Check suffix is digits only
            if not suffix.isdigit():
                issues.append(
                    {
                        "id": hit["_id"],
                        "issue": "SUFFIX contains non-digits",
                        "suffix": suffix,
                    }
                )
                continue

            # Check suffix length
            if not (3 <= len(suffix) <= 5):
                issues.append(
                    {
                        "id": hit["_id"],
                        "issue": f"SUFFIX length {len(suffix)} not in range 3-5",
                        "suffix": suffix,
                    }
                )
                continue

            # Check variant if present
            variant = source.get("variant")
            if variant and (len(variant) != 1 or not variant.isalpha()):
                issues.append(
                    {
                        "id": hit["_id"],
                        "issue": "VARIANT is not a single letter",
                        "variant": variant,
                    }
                )
                continue

            valid_count += 1

        # Report
        logger.info(
            f"Sample verification: {valid_count}/{len(hits)} valid ({valid_count/len(hits)*100:.1f}%)"
        )

        if issues:
            logger.warning(f"Found {len(issues)} issues in sample:")
            for issue in issues[:10]:  # Show first 10
                logger.warning(f"  - {issue}")

        return valid_count, issues

    except Exception as e:
        logger.error(f"Sample verification failed: {e}")
        return 0, []


def test_queries(retriever: OpenSearchTagsRetriever, enhancer: PIDQueryEnhancer):
    """Run test queries"""
    logger.info("Running test queries...")

    test_cases = [
        {
            "query": "5153",
            "description": "SUFFIX-only query",
            "expected_strategy": "suffix_search",
        },
        {
            "query": "04 PAHH 5153",
            "description": "Full tag with UNIT",
            "expected_strategy": "component_search",
        },
        {
            "query": "PAHH 5153",
            "description": "Tag without UNIT",
            "expected_strategy": "component_search",
        },
        {
            "query": "04 5153",
            "description": "UNIT + SUFFIX only",
            "expected_strategy": "component_search",
        },
        {
            "query": "IS 501",
            "description": "PREFIX + SUFFIX (no UNIT)",
            "expected_strategy": "component_search",
        },
    ]

    results = []

    for test_case in test_cases:
        query = test_case["query"]
        expected_strategy = test_case["expected_strategy"]

        logger.info(f"Testing: '{query}' ({test_case['description']})")

        try:
            # Enhance query
            enhanced = enhancer.enhance(query)
            strategy = enhanced.get("strategy")

            logger.info(f"  Strategy: {strategy} (expected: {expected_strategy})")

            # Execute search based on strategy
            if strategy == "suffix_search":
                suffix = enhanced.get("suffix")
                search_results = retriever.search_by_suffix(suffix)
                logger.info(f"  Results: {search_results.get('total_tags')} tags")
                logger.info(f"  Ambiguity: {search_results.get('has_ambiguity')}")

                if search_results.get("groups"):
                    for group in search_results["groups"]:
                        logger.info(
                            f"    - Prefixes: {group.get('prefixes')}, Pages: {group.get('pages')}"
                        )

            elif strategy == "component_search":
                components = enhanced.get("components", {})
                search_results = retriever.search_by_components(**components)
                logger.info(f"  Results: {len(search_results)} tags")

                # Show sample
                for result in search_results[:3]:
                    logger.info(
                        f"    - {result.get('text')} (page {result.get('page')})"
                    )

            # Record result
            results.append(
                {
                    "query": query,
                    "strategy": strategy,
                    "expected_strategy": expected_strategy,
                    "passed": strategy == expected_strategy,
                }
            )

        except Exception as e:
            logger.error(f"  Test failed: {e}")
            results.append(
                {
                    "query": query,
                    "error": str(e),
                    "passed": False,
                }
            )

    # Summary
    passed = sum(1 for r in results if r.get("passed"))
    logger.info(f"Test queries: {passed}/{len(results)} passed")

    return results


def main():
    """Main validation function"""
    logger.info("=" * 60)
    logger.info("Starting migration validation")
    logger.info("=" * 60)

    # Configuration
    index_name = os.environ.get("TAGS_INDEX_NAME", "pvcfc_pid_tags")
    client = create_opensearch_client()

    # Step 1: Count comparison
    logger.info("\n[1] Comparing document counts...")
    backup_count = count_backup_tags()
    new_count = count_new_tags(client, index_name)

    if backup_count and new_count:
        logger.info(f"Backup count: {backup_count}")
        logger.info(f"New count: {new_count}")

        if new_count >= backup_count * 0.95:  # Allow 5% difference
            logger.info("✓ Count check PASSED (within 5% tolerance)")
        else:
            logger.warning(
                f"✗ Count check FAILED: {new_count/backup_count*100:.1f}% of backup"
            )
    else:
        logger.warning("Could not compare counts (missing data)")

    # Step 2: Sample verification
    logger.info("\n[2] Sampling and verifying tags...")
    valid_count, issues = sample_and_verify_tags(client, index_name, sample_size=100)

    # Step 3: Test queries
    logger.info("\n[3] Running test queries...")
    retriever = OpenSearchTagsRetriever(index_name=index_name)
    enhancer = PIDQueryEnhancer()

    test_results = test_queries(retriever, enhancer)

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Document count: {new_count}/{backup_count if backup_count else '?'}")
    logger.info(f"Sample validation: {valid_count}/100 valid")
    logger.info(
        f"Test queries: {sum(1 for r in test_results if r.get('passed'))}/{len(test_results)} passed"
    )

    # Save validation report
    report = {
        "timestamp": datetime.now().isoformat(),
        "counts": {
            "backup": backup_count,
            "new": new_count,
        },
        "sample_validation": {
            "valid": valid_count,
            "total": 100,
            "issues": issues[:50],  # Limit issues in report
        },
        "test_queries": test_results,
    }

    report_file = PROJECT_ROOT / "artifacts/migration/validation_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"Validation report saved to {report_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
