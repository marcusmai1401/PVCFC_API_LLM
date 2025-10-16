"""
Backfill Tags Metadata to OpenSearch and Weaviate

Reads tags from chunks.jsonl and updates both indexes
This is a lightweight update (no re-embedding, no re-ingestion)
"""

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import weaviate
from loguru import logger
from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

from app.core.config import settings


def backfill_tags_to_indexes(
    chunks_file: Path = None,
    batch_size: int = 100,
    dry_run: bool = False,
):
    """
    Backfill tags metadata from chunks.jsonl to OpenSearch + Weaviate

    Args:
        chunks_file: Path to chunks.jsonl (default: artifacts/ingestion_production/chunks/chunks.jsonl)
        batch_size: Number of updates per batch
        dry_run: If True, only preview updates without applying

    Returns:
        True if successful
    """
    logger.info("=" * 80)
    logger.info("BACKFILLING TAGS TO INDEXES")
    logger.info("=" * 80)

    # Default chunks file
    if chunks_file is None:
        chunks_file = (
            PROJECT_ROOT / "artifacts/ingestion_production/chunks/chunks.jsonl"
        )

    if not chunks_file.exists():
        logger.error(f"Chunks file not found: {chunks_file}")
        return False

    logger.info(f"Chunks file: {chunks_file}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("")

    # Connect to OpenSearch
    logger.info("Connecting to OpenSearch...")
    opensearch_client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,
    )

    # Verify index exists
    if not opensearch_client.indices.exists(index=settings.opensearch_index):
        logger.error(f"OpenSearch index '{settings.opensearch_index}' does not exist!")
        return False

    logger.info(f"✅ OpenSearch connected: index={settings.opensearch_index}")

    # Connect to Weaviate
    logger.info("Connecting to Weaviate...")

    if settings.weaviate_use_grpc and settings.weaviate_grpc_port:
        weaviate_client = weaviate.connect_to_custom(
            http_host=settings.weaviate_host,
            http_port=settings.weaviate_port,
            http_secure=False,
            grpc_host=settings.weaviate_host,
            grpc_port=settings.weaviate_grpc_port,
            grpc_secure=False,
        )
    else:
        weaviate_client = weaviate.connect_to_local(
            host=settings.weaviate_host,
            port=settings.weaviate_port,
        )

    weaviate_collection = weaviate_client.collections.get(settings.weaviate_collection)

    logger.info(f"✅ Weaviate connected: collection={settings.weaviate_collection}")
    logger.info("")

    # Load and process chunks
    logger.info("Loading chunks...")

    updates_opensearch = []
    updates_weaviate = []
    stats = {
        "total_chunks": 0,
        "chunks_with_tags": 0,
        "chunks_without_tags": 0,
        "opensearch_updated": 0,
        "weaviate_updated": 0,
        "errors": 0,
    }

    with open(chunks_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(tqdm(f, desc="Processing chunks"), 1):
            try:
                chunk = json.loads(line)
                stats["total_chunks"] += 1

                chunk_id = chunk.get("chunk_id")
                if not chunk_id:
                    logger.warning(f"Line {line_num}: missing chunk_id, skipping")
                    continue

                # Get tags from metadata
                tags = chunk.get("metadata", {}).get("tags", [])
                tags_raw = chunk.get("metadata", {}).get("tags_raw", [])

                if not tags:
                    stats["chunks_without_tags"] += 1
                    continue

                stats["chunks_with_tags"] += 1

                # Preview for dry run
                if dry_run and stats["chunks_with_tags"] <= 5:
                    logger.info(f"Preview: chunk_id={chunk_id}, tags={tags}")

                # Prepare OpenSearch update
                updates_opensearch.append(
                    {
                        "_op_type": "update",
                        "_index": settings.opensearch_index,
                        "_id": chunk_id,
                        "doc": {"tags": tags, "tags_raw": tags_raw},
                    }
                )

                # Prepare Weaviate update
                updates_weaviate.append(
                    {"uuid": chunk_id, "properties": {"tags": tags}}
                )

                # Batch update
                if len(updates_opensearch) >= batch_size:
                    if not dry_run:
                        # OpenSearch bulk update
                        success, errors = helpers.bulk(
                            opensearch_client,
                            updates_opensearch,
                            raise_on_error=False,
                        )
                        stats["opensearch_updated"] += success

                        # Weaviate batch update
                        with weaviate_collection.batch.fixed_size(
                            batch_size=batch_size
                        ) as batch:
                            for upd in updates_weaviate:
                                try:
                                    batch.update_object(
                                        uuid=upd["uuid"], properties=upd["properties"]
                                    )
                                    stats["weaviate_updated"] += 1
                                except Exception as e:
                                    logger.warning(
                                        f"Weaviate update failed for {upd['uuid']}: {e}"
                                    )
                                    stats["errors"] += 1

                    # Reset batches
                    updates_opensearch = []
                    updates_weaviate = []

            except json.JSONDecodeError as e:
                logger.error(f"Line {line_num}: JSON decode error: {e}")
                stats["errors"] += 1
            except Exception as e:
                logger.error(f"Line {line_num}: Processing error: {e}")
                stats["errors"] += 1

    # Process remaining updates
    if updates_opensearch and not dry_run:
        logger.info("Processing final batch...")
        success, errors = helpers.bulk(
            opensearch_client, updates_opensearch, raise_on_error=False
        )
        stats["opensearch_updated"] += success

        with weaviate_collection.batch.fixed_size(batch_size=batch_size) as batch:
            for upd in updates_weaviate:
                try:
                    batch.update_object(uuid=upd["uuid"], properties=upd["properties"])
                    stats["weaviate_updated"] += 1
                except Exception as e:
                    logger.warning(f"Weaviate update failed for {upd['uuid']}: {e}")
                    stats["errors"] += 1

    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total chunks processed: {stats['total_chunks']}")
    logger.info(f"Chunks with tags: {stats['chunks_with_tags']}")
    logger.info(f"Chunks without tags: {stats['chunks_without_tags']}")

    if not dry_run:
        logger.info(f"OpenSearch updated: {stats['opensearch_updated']}")
        logger.info(f"Weaviate updated: {stats['weaviate_updated']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("")
        logger.info("✅ Backfill completed successfully")
    else:
        logger.info("")
        logger.info("DRY RUN: No updates applied")
        logger.info(f"Would update {stats['chunks_with_tags']} chunks")

    logger.info("=" * 80)

    # Cleanup
    weaviate_client.close()

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill tags to OpenSearch and Weaviate"
    )
    parser.add_argument(
        "--chunks-file",
        type=Path,
        default=None,
        help="Path to chunks.jsonl file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for updates (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview updates without applying",
    )

    args = parser.parse_args()

    success = backfill_tags_to_indexes(
        chunks_file=args.chunks_file,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    sys.exit(0 if success else 1)
