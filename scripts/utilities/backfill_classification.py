#!/usr/bin/env python
"""
Backfill classification metadata for existing documents

This script updates existing documents in OpenSearch and Weaviate with
default classification values (pending status) so they can be classified later.

Usage:
    python scripts/utilities/backfill_classification.py [--dry-run] [--batch-size 500]

Options:
    --dry-run       Show what would be updated without making changes
    --batch-size    Number of documents to process per batch (default: 500)

Requirements:
    pip install opensearch-py weaviate-client>=4.0.0
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from opensearchpy import OpenSearch
    from opensearchpy.helpers import bulk
except ImportError:
    logger.error("opensearch-py not installed!")
    sys.exit(1)

try:
    import weaviate
except ImportError:
    logger.error("weaviate-client not installed!")
    sys.exit(1)

from app.core.config import settings

# Default values for unclassified documents
DEFAULT_CLASSIFICATION = {
    "category": None,  # Will be set by classifier
    "classification_status": "pending",
    "classification_confidence": None,
    "classification_method": None,
}


def create_opensearch_client() -> OpenSearch:
    """Create OpenSearch client"""
    import os

    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,
    )
    return client


def connect_to_weaviate() -> weaviate.WeaviateClient:
    """Connect to Weaviate"""
    host = getattr(settings, "weaviate_host", "localhost")
    port = getattr(settings, "weaviate_port", 8080)
    return weaviate.connect_to_local(host=host, port=port)


def backfill_opensearch(
    client: OpenSearch,
    index_name: str = "rag_chunks",
    batch_size: int = 500,
    dry_run: bool = False,
) -> int:
    """
    Backfill classification fields in OpenSearch
    
    Updates documents that don't have classification_status field set.
    """
    logger.info(f"\n{'[DRY RUN] ' if dry_run else ''}Backfilling OpenSearch index: {index_name}")

    # Query for documents without classification_status
    query = {
        "query": {
            "bool": {
                "must_not": [
                    {"exists": {"field": "classification_status"}}
                ]
            }
        },
        "_source": ["doc_id", "chunk_id"],
        "size": batch_size,
    }

    total_updated = 0
    scroll_id = None

    try:
        # Initial search with scroll
        response = client.search(
            index=index_name,
            body=query,
            scroll="5m",
        )
        scroll_id = response.get("_scroll_id")
        hits = response["hits"]["hits"]

        while hits:
            logger.info(f"Processing batch of {len(hits)} documents...")

            if not dry_run:
                # Prepare bulk update actions
                actions = []
                for hit in hits:
                    action = {
                        "_op_type": "update",
                        "_index": index_name,
                        "_id": hit["_id"],
                        "doc": {
                            "classification_status": DEFAULT_CLASSIFICATION["classification_status"],
                        },
                    }
                    actions.append(action)

                # Execute bulk update
                success, failed = bulk(client, actions, raise_on_error=False)
                total_updated += success
                if failed:
                    logger.warning(f"  {len(failed)} documents failed to update")
            else:
                total_updated += len(hits)

            # Get next batch
            response = client.scroll(scroll_id=scroll_id, scroll="5m")
            scroll_id = response.get("_scroll_id")
            hits = response["hits"]["hits"]

    finally:
        # Clear scroll
        if scroll_id:
            try:
                client.clear_scroll(scroll_id=scroll_id)
            except Exception:
                pass

    return total_updated


def backfill_weaviate(
    client: weaviate.WeaviateClient,
    collection_name: str = "Chunk",
    batch_size: int = 500,
    dry_run: bool = False,
) -> int:
    """
    Backfill classification fields in Weaviate
    
    Updates objects that don't have classification_status property set.
    """
    logger.info(f"\n{'[DRY RUN] ' if dry_run else ''}Backfilling Weaviate collection: {collection_name}")

    if not client.collections.exists(collection_name):
        logger.error(f"Collection '{collection_name}' does not exist!")
        return 0

    collection = client.collections.get(collection_name)
    total_updated = 0

    try:
        # Fetch objects without classification_status
        # Note: Weaviate v4 doesn't have direct "field not exists" filter
        # We'll iterate and check each object
        
        offset = 0
        while True:
            # Fetch batch of objects
            response = collection.query.fetch_objects(
                limit=batch_size,
                offset=offset,
                return_properties=["doc_id", "classification_status"],
            )

            if not response.objects:
                break

            # Filter objects that need update
            objects_to_update = []
            for obj in response.objects:
                props = obj.properties
                if props.get("classification_status") is None:
                    objects_to_update.append(obj.uuid)

            if objects_to_update:
                logger.info(f"  Found {len(objects_to_update)} objects to update in batch")

                if not dry_run:
                    # Update each object
                    for uuid in objects_to_update:
                        try:
                            collection.data.update(
                                uuid=uuid,
                                properties={
                                    "classification_status": DEFAULT_CLASSIFICATION["classification_status"],
                                },
                            )
                            total_updated += 1
                        except Exception as e:
                            logger.warning(f"  Failed to update {uuid}: {e}")
                else:
                    total_updated += len(objects_to_update)

            offset += batch_size

            # Safety limit
            if offset > 1000000:
                logger.warning("Reached safety limit of 1M objects")
                break

    except Exception as e:
        logger.error(f"Error during Weaviate backfill: {e}")
        import traceback
        traceback.print_exc()

    return total_updated


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Backfill classification metadata for existing documents"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of documents to process per batch (default: 500)",
    )
    parser.add_argument(
        "--opensearch-only",
        action="store_true",
        help="Only update OpenSearch",
    )
    parser.add_argument(
        "--weaviate-only",
        action="store_true",
        help="Only update Weaviate",
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("BACKFILL CLASSIFICATION METADATA")
    logger.info("=" * 80)
    if args.dry_run:
        logger.info("MODE: DRY RUN (no changes will be made)")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info("=" * 80)

    os_updated = 0
    wv_updated = 0

    # OpenSearch backfill
    if not args.weaviate_only:
        try:
            os_client = create_opensearch_client()
            os_updated = backfill_opensearch(
                os_client,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )
            logger.info(f"OpenSearch: {'Would update' if args.dry_run else 'Updated'} {os_updated} documents")
        except Exception as e:
            logger.error(f"OpenSearch backfill failed: {e}")

    # Weaviate backfill
    if not args.opensearch_only:
        try:
            wv_client = connect_to_weaviate()
            try:
                wv_updated = backfill_weaviate(
                    wv_client,
                    batch_size=args.batch_size,
                    dry_run=args.dry_run,
                )
                logger.info(f"Weaviate: {'Would update' if args.dry_run else 'Updated'} {wv_updated} objects")
            finally:
                wv_client.close()
        except Exception as e:
            logger.error(f"Weaviate backfill failed: {e}")

    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"OpenSearch documents: {os_updated}")
    logger.info(f"Weaviate objects: {wv_updated}")
    logger.info(f"Total: {os_updated + wv_updated}")
    if args.dry_run:
        logger.info("\nThis was a dry run. Run without --dry-run to apply changes.")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
