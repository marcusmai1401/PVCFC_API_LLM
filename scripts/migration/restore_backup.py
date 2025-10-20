#!/usr/bin/env python
"""
Restore P&ID tags from backup

This script restores the old index from backup in case migration fails:
1. Deletes new index
2. Recreates old index with backup mapping
3. Restores data from backup JSONL
4. Verifies count
"""
import json
import os
import sys
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


def load_backup_manifest():
    """Load backup manifest"""
    manifest_file = PROJECT_ROOT / "artifacts/migration_backup/backup_manifest.json"

    if not manifest_file.exists():
        raise FileNotFoundError(f"Backup manifest not found: {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    logger.info(f"Loaded backup manifest from {manifest_file}")
    return manifest


def restore_index(
    client: OpenSearch, index_name: str, backup_dir: Path, manifest: dict
):
    """
    Restore index from backup

    Args:
        client: OpenSearch client
        index_name: Index name
        backup_dir: Backup directory
        manifest: Backup manifest
    """
    # Get backup files
    mapping_file = manifest["backups"].get("tags_mapping")
    data_file = manifest["backups"].get("tags_data")

    if not mapping_file or not data_file:
        raise ValueError("Missing backup files in manifest")

    mapping_path = backup_dir / mapping_file
    data_path = backup_dir / data_file

    # Step 1: Delete new index if exists
    if client.indices.exists(index=index_name):
        logger.warning(f"Deleting current index: {index_name}")
        client.indices.delete(index=index_name)
        logger.info("Current index deleted")

    # Step 2: Load old mapping
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping_response = json.load(f)

    # Extract mapping for the index (response format from OpenSearch)
    old_mapping = mapping_response.get(index_name, {})

    if not old_mapping:
        logger.error(f"Mapping for {index_name} not found in backup")
        raise ValueError(f"Invalid mapping backup")

    # Step 3: Create index with old mapping
    logger.info(f"Recreating index: {index_name}")
    client.indices.create(index=index_name, body=old_mapping)
    logger.info("Index recreated with old mapping")

    # Step 4: Restore data
    logger.info(f"Restoring data from {data_path}")

    actions = []
    total_restored = 0

    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            backup_doc = json.loads(line)

            action = {
                "_index": index_name,
                "_id": backup_doc["_id"],
                "_source": backup_doc["_source"],
            }

            actions.append(action)

            # Bulk insert in batches
            if len(actions) >= 1000:
                success, errors = helpers.bulk(client, actions, raise_on_error=False)
                total_restored += success
                logger.info(f"Restored batch: {success} documents")
                actions = []

    # Insert remaining
    if actions:
        success, errors = helpers.bulk(client, actions, raise_on_error=False)
        total_restored += success
        logger.info(f"Restored final batch: {success} documents")

    logger.info(f"Total documents restored: {total_restored}")

    # Step 5: Verify count
    client.indices.refresh(index=index_name)
    count_response = client.count(index=index_name)
    actual_count = count_response["count"]

    logger.info(f"Verification: expected={total_restored}, actual={actual_count}")

    if actual_count == total_restored:
        logger.info("✓ Restore verification PASSED")
        return True
    else:
        logger.warning(
            f"✗ Restore verification FAILED: {actual_count} != {total_restored}"
        )
        return False


def main():
    """Main restore function"""
    logger.info("=" * 60)
    logger.info("RESTORING P&ID TAGS FROM BACKUP")
    logger.info("=" * 60)
    logger.warning("This will DELETE the current index and restore from backup!")
    logger.warning("Make sure this is what you want to do.")

    # Configuration
    index_name = os.environ.get("TAGS_INDEX_NAME", "pvcfc_pid_tags")
    backup_dir = PROJECT_ROOT / "artifacts/migration_backup"

    # Load manifest
    try:
        manifest = load_backup_manifest()
    except Exception as e:
        logger.error(f"Failed to load backup manifest: {e}")
        sys.exit(1)

    # Create client
    client = create_opensearch_client()

    # Restore
    try:
        success = restore_index(client, index_name, backup_dir, manifest)

        if success:
            logger.info("=" * 60)
            logger.info("RESTORE COMPLETE!")
            logger.info(f"Index {index_name} has been restored from backup")
            logger.info("=" * 60)
        else:
            logger.error("RESTORE FAILED - verification did not pass")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
