"""
Bulk insert BM25 documents and metadata into OpenSearch

This script loads data from:
- artifacts/index_production/bm25/documents.json (text content)
- artifacts/index_production/bm25/metadata.json (chunk metadata)

And bulk inserts into OpenSearch 'rag_chunks' index with optimized settings.

Usage:
    python scripts/opensearch/bulk_insert_to_opensearch.py [--dry-run] [--batch-size 1000]

Requirements:
    pip install opensearch-py tqdm
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List

from loguru import logger
from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configuration
INDEX_NAME = "rag_chunks"
OS_HOST = "localhost"
OS_PORT = 9200

# Data paths
DOCS_PATH = project_root / "artifacts" / "index_production" / "bm25" / "documents.json"
META_PATH = project_root / "artifacts" / "index_production" / "bm25" / "metadata.json"


def create_opensearch_client():
    """Create OpenSearch client connection"""
    try:
        client = OpenSearch(
            hosts=[{"host": OS_HOST, "port": OS_PORT}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            timeout=60,
        )
        # Test connection
        info = client.info()
        logger.info(f"Connected to OpenSearch: {info['version']['number']}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch at {OS_HOST}:{OS_PORT}")
        logger.error(f"Error: {e}")
        sys.exit(1)


def load_data() -> tuple[List[str], List[Dict[str, Any]]]:
    """Load documents and metadata from JSON files"""
    logger.info("Loading data files...")

    if not DOCS_PATH.exists():
        logger.error(f"Documents file not found: {DOCS_PATH}")
        sys.exit(1)

    if not META_PATH.exists():
        logger.error(f"Metadata file not found: {META_PATH}")
        sys.exit(1)

    with open(DOCS_PATH, "r", encoding="utf-8") as f:
        documents = json.load(f)

    with open(META_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if len(documents) != len(metadata):
        logger.error(
            f"Data mismatch: {len(documents)} documents vs {len(metadata)} metadata"
        )
        sys.exit(1)

    logger.success(f"✓ Loaded {len(documents)} documents and metadata")
    return documents, metadata


def normalize_record(text: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a single document record for OpenSearch

    Handles:
    - Missing page field (derive from page_start or default to 1)
    - Null/None values
    - Type conversions
    - Field extraction from nested metadata
    """
    # Derive 'page' if not present
    page = meta.get("page")
    if page is None:
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")
        if page_start is not None:
            page = page_start
        elif page_end is not None:
            page = page_end
        else:
            page = 1

    # Extract page_nums (can be list or single value)
    page_nums = meta.get("page_nums")
    if isinstance(page_nums, list) and page_nums:
        page_nums = page_nums[0]
    elif page_nums is None:
        page_nums = page

    # Build normalized document
    doc = {
        # Core fields
        "text": text or "",
        "chunk_id": meta.get("chunk_id"),
        "doc_id": meta.get("doc_id"),
        # Chunk structure
        "chunk_index": meta.get("chunk_index", 0),
        "parent_chunk_id": meta.get("parent_chunk_id"),
        "level": meta.get("level"),
        # Content metadata
        "heading": meta.get("heading"),
        "title": meta.get("title"),
        "author": meta.get("author"),
        # Document metadata
        "doc_type": meta.get("doc_type"),
        "revision": meta.get("revision"),
        "source_format": meta.get("source_format"),
        "file_name": meta.get("file_name"),
        # Page information (critical for citations)
        "page": page,
        "page_start": meta.get("page_start"),
        "page_end": meta.get("page_end"),
        "page_nums": page_nums,
        # Table metadata
        "has_table": meta.get("has_table"),
        "table_count": meta.get("table_count"),
        "table_keywords": meta.get("table_keywords", []),
        "has_torque_data": meta.get("has_torque_data"),
        # Additional metadata
        "equipment_id": meta.get("equipment_id"),
        "language": meta.get("language"),
        "year": meta.get("year"),
    }

    # Remove None values to save space (OpenSearch handles missing fields)
    doc = {k: v for k, v in doc.items() if v is not None}

    return doc


def actions_generator(
    documents: List[str], metadata: List[Dict[str, Any]]
) -> Iterator[Dict[str, Any]]:
    """
    Generate bulk actions for OpenSearch

    Yields actions for helpers.bulk()
    """
    for i, (text, meta) in enumerate(zip(documents, metadata)):
        body = normalize_record(text, meta)

        # Use chunk_id as document ID, fallback to index
        _id = body.get("chunk_id") or f"rag_{i}"

        yield {
            "_op_type": "index",
            "_index": INDEX_NAME,
            "_id": _id,
            "_source": body,
        }


def verify_index_exists(client: OpenSearch) -> bool:
    """Check if the target index exists"""
    exists = client.indices.exists(index=INDEX_NAME)
    if not exists:
        logger.error(f"Index '{INDEX_NAME}' does not exist")
        logger.error("Please run: python scripts/opensearch/create_rag_chunks_index.py")
        return False
    return True


def bulk_insert(
    client: OpenSearch,
    documents: List[str],
    metadata: List[Dict[str, Any]],
    batch_size: int = 1000,
    dry_run: bool = False,
) -> bool:
    """
    Perform bulk insert with optimized settings

    Steps:
    1. Disable refresh during bulk insert (for speed)
    2. Bulk insert in batches
    3. Re-enable refresh
    4. Force refresh to make data searchable
    """
    total = len(documents)
    logger.info(f"Preparing to insert {total} documents into '{INDEX_NAME}'")

    if dry_run:
        logger.warning("DRY RUN mode - no data will be inserted")
        # Show sample
        gen = actions_generator(documents[:5], metadata[:5])
        for i, action in enumerate(gen, 1):
            logger.info(f"\nSample action {i}:")
            logger.info(json.dumps(action["_source"], indent=2, ensure_ascii=False))
        return True

    try:
        # Step 1: Disable refresh for faster bulk indexing
        logger.info("Disabling refresh interval for bulk insert...")
        client.indices.put_settings(
            index=INDEX_NAME, body={"index": {"refresh_interval": "-1"}}
        )

        # Step 2: Bulk insert with progress bar
        logger.info(f"Bulk inserting {total} documents (batch_size={batch_size})...")

        success_count = 0
        error_count = 0

        # Use helpers.bulk with progress tracking
        with tqdm(total=total, desc="Indexing", unit="docs") as pbar:
            for ok, response in helpers.streaming_bulk(
                client,
                actions_generator(documents, metadata),
                index=INDEX_NAME,
                chunk_size=batch_size,
                request_timeout=120,
                raise_on_error=False,
                raise_on_exception=False,
            ):
                if ok:
                    success_count += 1
                else:
                    error_count += 1
                    # Log first few errors
                    if error_count <= 5:
                        logger.error(f"Indexing error: {response}")

                pbar.update(1)

        # Step 3: Restore refresh interval
        logger.info("Restoring refresh interval...")
        client.indices.put_settings(
            index=INDEX_NAME, body={"index": {"refresh_interval": "1s"}}
        )

        # Step 4: Force refresh to make data searchable
        logger.info("Refreshing index...")
        client.indices.refresh(index=INDEX_NAME)

        # Verify count
        count_result = client.count(index=INDEX_NAME)
        actual_count = count_result["count"]

        logger.success(
            f"\n✓ Bulk insert completed: {success_count} success, {error_count} errors"
        )
        logger.info(f"Index '{INDEX_NAME}' now has {actual_count} documents")

        if actual_count != total:
            logger.warning(
                f"Count mismatch: expected {total}, got {actual_count}. "
                f"Check errors above."
            )

        return error_count == 0

    except Exception as e:
        logger.error(f"Bulk insert failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Bulk insert BM25 data into OpenSearch rag_chunks index"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview data without inserting (shows first 5 records)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of documents per batch (default: 1000)",
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("OpenSearch Bulk Insert - rag_chunks")
    logger.info("=" * 80)

    # Create client
    client = create_opensearch_client()

    # Verify index exists
    if not verify_index_exists(client):
        sys.exit(1)

    # Load data
    documents, metadata = load_data()

    # Perform bulk insert
    success = bulk_insert(
        client, documents, metadata, batch_size=args.batch_size, dry_run=args.dry_run
    )

    if success:
        logger.success("\n✓ Data insertion completed successfully")
        if not args.dry_run:
            logger.info("\nNext step: Test search with test_opensearch_search.py")
    else:
        logger.error("\n✗ Data insertion completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
