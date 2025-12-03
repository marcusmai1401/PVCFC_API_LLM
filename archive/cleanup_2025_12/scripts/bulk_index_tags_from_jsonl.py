#!/usr/bin/env python
"""
Bulk Index Tags from JSONL to OpenSearch
Read tags from output/pid_ingestion/tags.jsonl and bulk index to OpenSearch

Usage:
    python scripts/bulk_index_tags_from_jsonl.py [--dry-run] [--batch-size 1000]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List

from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Fix Windows console encoding
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Configuration
INDEX_NAME = "rag_chunks"
TAGS_JSONL_PATH = PROJECT_ROOT / "output" / "pid_ingestion" / "tags.jsonl"


def create_opensearch_client(host: str = "localhost", port: int = 9200) -> OpenSearch:
    """Create OpenSearch client connection"""
    try:
        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            timeout=60,
        )
        # Test connection
        info = client.info()
        print(f"[OK] Connected to OpenSearch: {info['version']['number']}")
        return client
    except Exception as e:
        print(f"[ERROR] Failed to connect to OpenSearch at {host}:{port}")
        print(f"Error: {e}")
        sys.exit(1)


def load_tags_from_jsonl(jsonl_path: Path) -> List[Dict[str, Any]]:
    """Load tags from JSONL file"""
    print(f"[INFO] Loading tags from: {jsonl_path}")

    if not jsonl_path.exists():
        print(f"[ERROR] File not found: {jsonl_path}")
        sys.exit(1)

    tags = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                tag = json.loads(line.strip())
                tags.append(tag)
            except json.JSONDecodeError as e:
                print(f"[WARNING] JSON decode error at line {line_num}: {e}")

    print(f"[OK] Loaded {len(tags)} tags")
    return tags


def transform_tag_to_opensearch(tag: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform tag from JSONL format to OpenSearch document format

    Input format (from tags.jsonl):
    {
        "doc_id": "AMMONIA",
        "page": 3,
        "tag": "04 PI 2504",
        "unit": "04",
        "prefix": "PI",
        "suffix": "2504",
        "variant": null,
        "annotation": null,
        "bbox": [x0, y0, x1, y1],
        "confidence": 0.72,
        "has_variant": false,
        "has_annotation": false
    }

    Output format (for OpenSearch):
    {
        "chunk_id": "TAG_AMMONIA_p3_04_PI_2504",
        "doc_id": "AMMONIA",
        "page": 3,
        "text": "Equipment tag: 04 PI 2504",
        "tags": ["04 PI 2504"],
        "tags_raw": ["04 PI 2504"],
        "is_tag_entity": true,
        "tag_metadata": {
            "unit": "04",
            "prefix": "PI",
            "suffix": "2504",
            "variant": null,
            "annotation": null,
            "bbox": [x0, y0, x1, y1],
            "confidence": 0.72,
            "has_variant": false,
            "has_annotation": false
        }
    }
    """
    # Create unique chunk_id for the tag
    tag_normalized = tag["tag"].replace(" ", "_").replace("/", "_")
    chunk_id = f"TAG_{tag['doc_id']}_p{tag['page']}_{tag_normalized}"

    # Build OpenSearch document
    doc = {
        "chunk_id": chunk_id,
        "doc_id": tag["doc_id"],
        "page": tag["page"],
        "text": f"Equipment tag: {tag['tag']}",
        "tags": [tag["tag"]],
        "tags_raw": [tag["tag"]],
        "is_tag_entity": True,  # Flag to identify tag documents
        "tag_metadata": {
            "unit": tag.get("unit"),
            "prefix": tag.get("prefix"),
            "suffix": tag.get("suffix"),
            "variant": tag.get("variant"),
            "annotation": tag.get("annotation"),
            "bbox": tag.get("bbox"),
            "confidence": tag.get("confidence"),
            "has_variant": tag.get("has_variant", False),
            "has_annotation": tag.get("has_annotation", False),
        },
    }

    return doc


def actions_generator(tags: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """Generate bulk actions for OpenSearch"""
    for tag in tags:
        doc = transform_tag_to_opensearch(tag)

        yield {
            "_op_type": "index",
            "_index": INDEX_NAME,
            "_id": doc["chunk_id"],
            "_source": doc,
        }


def verify_index_exists(client: OpenSearch) -> bool:
    """Check if the target index exists"""
    exists = client.indices.exists(index=INDEX_NAME)
    if not exists:
        print(f"[ERROR] Index '{INDEX_NAME}' does not exist")
        print("Please run: python scripts/opensearch/create_rag_chunks_index.py")
        return False
    return True


def bulk_insert_tags(
    client: OpenSearch,
    tags: List[Dict[str, Any]],
    batch_size: int = 1000,
    dry_run: bool = False,
) -> bool:
    """
    Perform bulk insert of tags

    Steps:
    1. Transform tags to OpenSearch format
    2. Bulk insert in batches
    3. Refresh index
    4. Verify count
    """
    total = len(tags)
    print(f"[INFO] Preparing to insert {total} tags into '{INDEX_NAME}'")

    if dry_run:
        print("[DRY RUN] Preview mode - no data will be inserted")
        print("\nFirst 3 transformed documents:")
        for i, tag in enumerate(tags[:3], 1):
            doc = transform_tag_to_opensearch(tag)
            print(f"\n--- Document {i} ---")
            print(json.dumps(doc, indent=2, ensure_ascii=False))
        return True

    try:
        # Bulk insert with progress bar
        print(f"[INFO] Bulk inserting {total} tags (batch_size={batch_size})...")

        success_count = 0
        error_count = 0
        errors = []

        # Use helpers.streaming_bulk with progress tracking
        with tqdm(total=total, desc="Indexing tags", unit="tags") as pbar:
            for ok, response in helpers.streaming_bulk(
                client,
                actions_generator(tags),
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
                        errors.append(response)
                        print(f"\n[ERROR] Indexing error: {response}")

                pbar.update(1)

        # Refresh index to make data searchable
        print("[INFO] Refreshing index...")
        client.indices.refresh(index=INDEX_NAME)

        # Verify count
        result = client.count(
            index=INDEX_NAME, body={"query": {"term": {"is_tag_entity": True}}}
        )
        tag_count = result["count"]

        print("\n" + "=" * 80)
        print("[OK] Bulk insert completed!")
        print("=" * 80)
        print(f"Success: {success_count}")
        print(f"Errors: {error_count}")
        print(f"Total tag entities in index: {tag_count}")

        if error_count > 0:
            print(f"\n[WARNING] {error_count} errors occurred during indexing")
            if errors:
                print("\nFirst few errors:")
                for err in errors[:3]:
                    print(f"  {err}")

        return error_count == 0

    except Exception as e:
        print(f"[ERROR] Bulk insert failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def verify_sample_tags(client: OpenSearch, tags: List[Dict[str, Any]]):
    """Verify that sample tags were indexed correctly"""
    print("\n" + "=" * 80)
    print("VERIFICATION: Checking sample tags")
    print("=" * 80)

    # Sample a few tags to verify
    sample_tags = tags[:5]

    for i, tag in enumerate(sample_tags, 1):
        tag_text = tag["tag"]
        page = tag["page"]

        # Search for the tag
        result = client.search(
            index=INDEX_NAME,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"is_tag_entity": True}},
                            {"match": {"tags": tag_text}},
                        ]
                    }
                },
                "size": 1,
            },
        )

        if result["hits"]["total"]["value"] > 0:
            hit = result["hits"]["hits"][0]
            indexed_page = hit["_source"]["page"]
            print(f"[OK] {i}. Tag '{tag_text}' found (page {indexed_page})")
        else:
            print(f"[FAIL] {i}. Tag '{tag_text}' NOT found (expected page {page})")

    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Bulk index tags from JSONL to OpenSearch"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview data without inserting (shows first 3 records)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of tags per batch (default: 1000)",
    )
    parser.add_argument(
        "--jsonl-path",
        type=str,
        default=str(TAGS_JSONL_PATH),
        help=f"Path to tags JSONL file (default: {TAGS_JSONL_PATH})",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="OpenSearch host (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9200,
        help="OpenSearch port (default: 9200)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("BULK INDEX TAGS FROM JSONL TO OPENSEARCH")
    print("=" * 80)
    print(f"JSONL file: {args.jsonl_path}")
    print(f"OpenSearch: {args.host}:{args.port}")
    print(f"Index: {INDEX_NAME}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 80 + "\n")

    # Create client
    client = create_opensearch_client(args.host, args.port)

    # Verify index exists
    if not verify_index_exists(client):
        sys.exit(1)

    # Load tags
    jsonl_path = Path(args.jsonl_path)
    tags = load_tags_from_jsonl(jsonl_path)

    if not tags:
        print("[ERROR] No tags to index")
        sys.exit(1)

    # Show statistics
    doc_ids = set(tag["doc_id"] for tag in tags)
    pages = set(tag["page"] for tag in tags)
    print(f"\n[INFO] Statistics:")
    print(f"  Total tags: {len(tags)}")
    print(f"  Documents: {len(doc_ids)}")
    print(f"  Pages: {len(pages)}")
    print(f"  Page range: {min(pages)} - {max(pages)}")
    print()

    # Perform bulk insert
    success = bulk_insert_tags(
        client,
        tags,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    if success:
        if not args.dry_run:
            # Verify sample tags
            verify_sample_tags(client, tags)

        print("[OK] Indexing completed successfully!")
        print("\nNext steps:")
        print("  1. Test tag search: python scripts/test/test_instrument_retrieval.py")
        print("  2. Verify via API: python scripts/test/test_retrieval_via_api.py")
        print()
    else:
        print("[ERROR] Indexing completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
