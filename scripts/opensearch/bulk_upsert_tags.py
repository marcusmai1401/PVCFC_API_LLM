#!/usr/bin/env python
"""
Bulk Upsert Tags to OpenSearch
Load tags from entities/tags.jsonl into pvcfc_pid_tags index

Usage:
    python scripts/opensearch/bulk_upsert_tags.py [--tags-file path/to/tags.jsonl]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from loguru import logger
from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_config


def create_opensearch_client() -> OpenSearch:
    """Create OpenSearch client"""
    import os

    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        timeout=30,
        max_retries=3,
        retry_on_timeout=True,
    )

    try:
        client.info()
        return client
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch: {e}")
        sys.exit(1)


def load_tags(tags_file: Path) -> List[Dict]:
    """Load tags from JSONL file"""
    tags = []

    if not tags_file.exists():
        logger.warning(f"Tags file not found: {tags_file}")
        return tags

    with open(tags_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tag_data = json.loads(line)
                tags.append(tag_data)

    logger.info(f"Loaded {len(tags)} tags from {tags_file.name}")
    return tags


def bulk_upsert_tags(
    client: OpenSearch,
    index_name: str,
    tags: List[Dict],
    batch_size: int = 1000,
) -> Tuple[int, int]:
    """
    Bulk upsert tags to index

    Args:
        client: OpenSearch client
        index_name: Index name
        tags: List of tag dicts
        batch_size: Batch size for bulk operations

    Returns:
        (success_count, error_count)
    """
    if not tags:
        logger.warning("No tags to upsert")
        return 0, 0

    # Prepare bulk actions
    actions = []
    ts_ingest = datetime.utcnow().isoformat()

    for tag in tags:
        # Generate deterministic _id
        doc_id = tag.get("doc_id", "unknown")
        page = tag.get("page", 1)
        tag_text = tag.get("tag", "")

        # _id format: {doc_id}#{page}#{tag}
        # Hash if too long
        tag_id = f"{doc_id}#{page}#{tag_text}"
        if len(tag_id) > 512:
            import hashlib

            tag_id = hashlib.md5(tag_id.encode()).hexdigest()

        # Add timestamp
        tag["ts_ingest"] = ts_ingest

        action = {
            "_op_type": "index",  # Upsert (create or update)
            "_index": index_name,
            "_id": tag_id,
            "_source": tag,
        }
        actions.append(action)

    # Bulk insert with progress bar
    success_count = 0
    error_count = 0

    logger.info(f"Upserting {len(actions)} tags in batches of {batch_size}...")

    with tqdm(total=len(actions), desc="Upserting tags") as pbar:
        for i in range(0, len(actions), batch_size):
            batch = actions[i : i + batch_size]

            try:
                success, errors = helpers.bulk(
                    client,
                    batch,
                    raise_on_error=False,
                    raise_on_exception=False,
                )

                success_count += success
                error_count += len(errors) if errors else 0

                pbar.update(len(batch))

            except Exception as e:
                logger.error(f"Bulk batch failed: {e}")
                error_count += len(batch)
                pbar.update(len(batch))

    # Refresh index
    client.indices.refresh(index=index_name)

    logger.info(f"✓ Upserted: {success_count} tags")
    if error_count > 0:
        logger.warning(f"✗ Errors: {error_count}")

    return success_count, error_count


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Bulk upsert tags to OpenSearch")
    parser.add_argument(
        "--tags-file",
        type=Path,
        default=None,
        help="Path to tags.jsonl file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for bulk operations",
    )

    args = parser.parse_args()

    # Get config
    config = get_config()

    # Default tags file
    if args.tags_file is None:
        args.tags_file = config.ENTITIES_DIR / "tags.jsonl"

    index_name = config.TAGS_INDEX_NAME

    logger.info("=" * 80)
    logger.info("BULK UPSERT TAGS TO OPENSEARCH")
    logger.info("=" * 80)
    logger.info(f"Index: {index_name}")
    logger.info(f"Tags file: {args.tags_file}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info("=" * 80)

    # Create client
    client = create_opensearch_client()

    # Check if index exists
    if not client.indices.exists(index=index_name):
        logger.error(f"Index does not exist: {index_name}")
        logger.error("Run create_tags_index.py first")
        sys.exit(1)

    # Load tags
    tags = load_tags(args.tags_file)

    if not tags:
        logger.warning("No tags to upsert")
        sys.exit(0)

    # Bulk upsert
    success, errors = bulk_upsert_tags(
        client,
        index_name,
        tags,
        args.batch_size,
    )

    logger.info("=" * 80)
    logger.info(f"✓ Bulk upsert complete!")
    logger.info(f"  Success: {success}")
    logger.info(f"  Errors: {errors}")
    logger.info("=" * 80)

    sys.exit(0 if errors == 0 else 1)


if __name__ == "__main__":
    main()
