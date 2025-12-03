#!/usr/bin/env python
"""
Re-index tags to OpenSearch with new schema

This script:
1. Deletes old index (pvcfc_pid_tags)
2. Creates new index with updated mapping
3. Bulk inserts from tags_new_schema.jsonl
4. Verifies document count
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from loguru import logger
from opensearchpy import OpenSearch, helpers


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


def load_new_mapping() -> dict:
    """Load updated mapping from config"""
    mapping_file = PROJECT_ROOT / "config/tags_index_mapping.json"

    with open(mapping_file, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    logger.info(f"Loaded updated mapping from {mapping_file}")
    return mapping


def delete_old_index(client: OpenSearch, index_name: str):
    """Delete old index if exists"""
    if client.indices.exists(index=index_name):
        logger.warning(f"Deleting old index: {index_name}")
        client.indices.delete(index=index_name)
        logger.info(f"Old index deleted: {index_name}")
    else:
        logger.info(f"Old index not found: {index_name}")


def create_new_index(client: OpenSearch, index_name: str, mapping: dict):
    """Create new index with updated mapping"""
    logger.info(f"Creating new index: {index_name}")

    client.indices.create(index=index_name, body=mapping)

    logger.info(f"New index created: {index_name}")


def bulk_insert_tags(client: OpenSearch, index_name: str, tags_file: Path):
    """
    Bulk insert tags from JSONL file

    Args:
        client: OpenSearch client
        index_name: Index name
        tags_file: Path to tags_new_schema.jsonl
    """
    logger.info(f"Bulk inserting tags from {tags_file}")

    if not tags_file.exists():
        raise FileNotFoundError(f"Tags file not found: {tags_file}")

    # Read tags and prepare bulk actions
    actions = []
    total_lines = 0

    with open(tags_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue

            total_lines += 1
            tag_data = json.loads(line)

            # Build document ID: {doc_id}#{page}#{tag}
            doc_id = tag_data.get("doc_id", "unknown")
            page = tag_data.get("page", 0)
            tag_text = tag_data.get("tag", "")

            # Create deterministic ID
            tag_hash = abs(hash(tag_text)) % (10**8)
            doc_id_str = f"{doc_id}#{page}#{tag_hash}"

            # Flatten parts into top level for easier querying
            parts = tag_data.get("parts", {})

            action = {
                "_index": index_name,
                "_id": doc_id_str,
                "_source": {
                    "doc_id": doc_id,
                    "page": page,
                    "tag": tag_text,
                    # Component fields at top level
                    "unit": parts.get("unit"),
                    "prefix": parts.get("prefix"),
                    "suffix": parts.get("suffix"),
                    "variant": parts.get("variant"),
                    "annotation": parts.get("annotation"),
                    # Other fields
                    "bbox": tag_data.get("bbox"),
                    "rotation": tag_data.get("rotation", 0.0),
                    "confidence": tag_data.get("confidence", 1.0),
                    "evidence_span_ids": tag_data.get("evidence_span_ids", []),
                    "has_variant": tag_data.get("has_variant", False),
                    "has_annotation": tag_data.get("has_annotation", False),
                    "crop_path": tag_data.get("crop_path"),
                    "ts_ingest": datetime.now().isoformat(),
                },
            }

            actions.append(action)

            # Bulk insert in batches of 1000
            if len(actions) >= 1000:
                success, errors = helpers.bulk(client, actions, raise_on_error=False)
                logger.info(f"Inserted batch: {success} success, {len(errors)} errors")
                actions = []

    # Insert remaining
    if actions:
        success, errors = helpers.bulk(client, actions, raise_on_error=False)
        logger.info(f"Inserted final batch: {success} success, {len(errors)} errors")

    logger.info(f"Bulk insert complete: {total_lines} tags processed")

    return total_lines


def verify_index(client: OpenSearch, index_name: str, expected_count: int):
    """Verify indexed document count"""
    logger.info("Verifying index...")

    # Refresh index
    client.indices.refresh(index=index_name)

    # Get count
    count_response = client.count(index=index_name)
    actual_count = count_response["count"]

    logger.info(f"Expected count: {expected_count}")
    logger.info(f"Actual count: {actual_count}")

    if actual_count == expected_count:
        logger.info("✓ Count verification PASSED")
        return True
    else:
        logger.warning(
            f"✗ Count verification FAILED: {actual_count} != {expected_count}"
        )
        return False


def main():
    """Main re-indexing function"""
    # Configuration
    index_name = os.environ.get("TAGS_INDEX_NAME", "pvcfc_pid_tags")
    tags_file = PROJECT_ROOT / "artifacts/migration/tags_new_schema.jsonl"

    logger.info("=" * 60)
    logger.info("Starting P&ID tags re-indexing with new schema")
    logger.info("=" * 60)

    # Check if tags file exists
    if not tags_file.exists():
        logger.error(f"Tags file not found: {tags_file}")
        logger.error("Please run reextract_tags.py first!")
        sys.exit(1)

    # Create client
    client = create_opensearch_client()

    # Load new mapping
    mapping = load_new_mapping()

    # Step 1: Delete old index
    delete_old_index(client, index_name)

    # Step 2: Create new index
    create_new_index(client, index_name, mapping)

    # Step 3: Bulk insert
    inserted_count = bulk_insert_tags(client, index_name, tags_file)

    # Step 4: Verify
    verify_result = verify_index(client, index_name, inserted_count)

    logger.info("=" * 60)
    logger.info("Re-indexing complete!")
    logger.info(f"Index: {index_name}")
    logger.info(f"Documents: {inserted_count}")
    logger.info(f"Verification: {'PASSED' if verify_result else 'FAILED'}")
    logger.info("=" * 60)

    if not verify_result:
        logger.error("Verification failed! Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
