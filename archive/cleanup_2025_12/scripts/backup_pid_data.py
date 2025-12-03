#!/usr/bin/env python
"""
Backup current P&ID tags data before migration
Backs up both the OpenSearch tags index and related chunk data
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
from opensearchpy import OpenSearch


def backup_tags_index(output_dir: Path, index_name: str = "pvcfc_pid_tags"):
    """
    Export current tags index to JSONL

    Args:
        output_dir: Output directory for backup
        index_name: OpenSearch index name

    Returns:
        Path to backup file
    """
    logger.info(f"Backing up tags index: {index_name}")

    # Connect to OpenSearch
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        timeout=30,
    )

    # Check if index exists
    if not client.indices.exists(index=index_name):
        logger.warning(f"Index {index_name} does not exist, skipping backup")
        return None

    # Get total count
    count_response = client.count(index=index_name)
    total_docs = count_response["count"]
    logger.info(f"Total documents to backup: {total_docs}")

    # Prepare backup file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = output_dir / f"tags_backup_{timestamp}.jsonl"

    # Scroll through all documents
    page_size = 1000
    scroll_time = "5m"

    response = client.search(
        index=index_name,
        body={
            "query": {"match_all": {}},
            "size": page_size,
            "_source": True,
        },
        scroll=scroll_time,
    )

    scroll_id = response["_scroll_id"]
    hits = response["hits"]["hits"]

    backed_up = 0

    with open(backup_file, "w", encoding="utf-8") as f:
        while hits:
            for hit in hits:
                # Write document with ID
                backup_doc = {
                    "_id": hit["_id"],
                    "_source": hit["_source"],
                }
                f.write(json.dumps(backup_doc, ensure_ascii=False) + "\n")
                backed_up += 1

            # Progress
            if backed_up % 1000 == 0:
                logger.info(f"Backed up {backed_up}/{total_docs} documents...")

            # Get next batch
            response = client.scroll(scroll_id=scroll_id, scroll=scroll_time)
            scroll_id = response["_scroll_id"]
            hits = response["hits"]["hits"]

    # Clear scroll
    client.clear_scroll(scroll_id=scroll_id)

    logger.info(f"Backup complete: {backed_up} documents saved to {backup_file}")

    return backup_file


def backup_index_mapping(output_dir: Path, index_name: str = "pvcfc_pid_tags"):
    """
    Backup index mapping configuration

    Args:
        output_dir: Output directory
        index_name: Index name

    Returns:
        Path to mapping file
    """
    logger.info(f"Backing up index mapping: {index_name}")

    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        timeout=30,
    )

    if not client.indices.exists(index=index_name):
        logger.warning(f"Index {index_name} does not exist, skipping mapping backup")
        return None

    # Get mapping
    mapping = client.indices.get_mapping(index=index_name)

    # Save mapping
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mapping_file = output_dir / f"tags_mapping_{timestamp}.json"

    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    logger.info(f"Mapping backed up to {mapping_file}")

    return mapping_file


def backup_doc_id_map(output_dir: Path):
    """
    Backup doc_id_map.json if it exists

    Args:
        output_dir: Output directory

    Returns:
        Path to backup file or None
    """
    logger.info("Backing up doc_id_map.json")

    # Check production path first
    production_path = PROJECT_ROOT / "artifacts/ingestion_production/doc_id_map.json"
    legacy_path = PROJECT_ROOT / "artifacts/ingestion/doc_id_map.json"

    source_path = None
    if production_path.exists():
        source_path = production_path
    elif legacy_path.exists():
        source_path = legacy_path

    if not source_path:
        logger.warning("No doc_id_map.json found, skipping")
        return None

    # Copy to backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = output_dir / f"doc_id_map_{timestamp}.json"

    import shutil

    shutil.copy2(source_path, backup_path)

    logger.info(f"doc_id_map backed up to {backup_path}")

    return backup_path


def main():
    """Main backup function"""
    # Create backup directory
    backup_dir = PROJECT_ROOT / "artifacts/migration_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting P&ID data backup to {backup_dir}")

    # Backup tags index
    tags_backup = backup_tags_index(backup_dir)

    # Backup mapping
    mapping_backup = backup_index_mapping(backup_dir)

    # Backup doc_id_map
    doc_id_map_backup = backup_doc_id_map(backup_dir)

    # Create backup manifest
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "backups": {
            "tags_data": str(tags_backup.name) if tags_backup else None,
            "tags_mapping": str(mapping_backup.name) if mapping_backup else None,
            "doc_id_map": str(doc_id_map_backup.name) if doc_id_map_backup else None,
        },
    }

    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info(f"Backup manifest saved to {manifest_file}")
    logger.info("=" * 60)
    logger.info("Backup complete! Files saved in artifacts/migration_backup/")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
