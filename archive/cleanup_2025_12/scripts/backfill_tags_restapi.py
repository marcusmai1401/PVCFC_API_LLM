"""
Backfill Tags Metadata using REST API Only

This version uses REST API calls instead of Python clients to avoid dependency issues
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
from loguru import logger
from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings


def _detect_weaviate_class(
    weaviate_base_url: str, preferred: Optional[str]
) -> Optional[str]:
    """Detect the correct class name to use for updates.
    Returns preferred if present in schema; otherwise, if only one class exists, return it; else try 'Chunk'.
    """
    try:
        resp = requests.get(f"{weaviate_base_url}/v1/schema", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        classes = [c.get("class") for c in data.get("classes", [])]
        if preferred and preferred in classes:
            return preferred
        if len(classes) == 1:
            return classes[0]
        if "Chunk" in classes:
            return "Chunk"
        return None
    except Exception as e:
        logger.warning(f"Failed to detect Weaviate class from schema: {e}")
        return preferred


def _graphql_query(
    weaviate_base_url: str, query: str, variables: Optional[dict] = None
) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    r = requests.post(
        f"{weaviate_base_url}/v1/graphql",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"GraphQL error {r.status_code}: {r.text[:300]}")
    out = r.json()
    if "errors" in out:
        raise RuntimeError(f"GraphQL response errors: {out['errors']}")
    return out


def _normalize_text(text: str) -> str:
    """Normalize text for matching: strip whitespace, collapse spaces, lowercase"""
    if not text:
        return ""
    # Strip leading/trailing whitespace
    text = text.strip()
    # Collapse multiple whitespaces/newlines to single space
    text = re.sub(r"\s+", " ", text)
    # Lowercase for case-insensitive matching
    text = text.lower()
    return text


def _build_doc_text_id_map(
    weaviate_base_url: str, class_name: str, doc_id: str
) -> tuple[Dict[str, str], Dict[str, str], Dict[int, str]]:
    """Fetch all objects for a doc_id and build mapping text->uuid.
    Returns: (exact_map, normalized_map, page_map) where:
    - exact_map: exact text -> uuid
    - normalized_map: normalized text -> uuid
    - page_map: page number -> first uuid on that page
    """
    exact_map: Dict[str, str] = {}
    normalized_map: Dict[str, str] = {}
    page_map: Dict[int, str] = {}
    limit = 200
    offset = 0
    while True:
        # Inline doc_id to avoid custom scalar variable type issues in Weaviate GraphQL
        escaped_doc_id = doc_id.replace("\\", "\\\\").replace('"', '\\"')
        query = (
            f'{{ Get {{ {class_name}(where: {{ path: ["doc_id"], operator: Equal, valueText: "{escaped_doc_id}" }}, limit: {limit}, offset: {offset}) '
            "{ _additional { id } doc_id page text } } }"
        )
        data = _graphql_query(
            weaviate_base_url,
            query,
        )
        items: List[dict] = data.get("data", {}).get("Get", {}).get(class_name, [])
        if not items:
            break
        for it in items:
            uid = it.get("_additional", {}).get("id")
            txt = it.get("text", "")
            page = it.get("page")
            if uid is None:
                continue
            # Store exact match
            exact_map[txt] = uid
            # Store normalized match
            normalized_key = _normalize_text(txt)
            if normalized_key:
                normalized_map[normalized_key] = uid
            # Store page match (first UUID per page)
            if page is not None and page not in page_map:
                page_map[page] = uid
        if len(items) < limit:
            break
        offset += limit
    return exact_map, normalized_map, page_map


def backfill_tags_restapi(
    chunks_file: Path = None,
    batch_size: int = 100,
    dry_run: bool = False,
):
    """
    Backfill tags using REST API for Weaviate

    Args:
        chunks_file: Path to chunks.jsonl
        batch_size: Batch size for updates
        dry_run: Preview only mode

    Returns:
        True if successful
    """
    logger.info("=" * 80)
    logger.info("BACKFILLING TAGS (REST API Mode)")
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

    if not opensearch_client.indices.exists(index=settings.opensearch_index):
        logger.error(f"OpenSearch index '{settings.opensearch_index}' does not exist!")
        return False

    logger.info(f"✅ OpenSearch connected: index={settings.opensearch_index}")

    # Weaviate REST API endpoint
    weaviate_base_url = f"http://{settings.weaviate_host}:{settings.weaviate_port}"
    logger.info(f"✅ Weaviate endpoint: {weaviate_base_url}")

    # Detect class name
    class_name = _detect_weaviate_class(weaviate_base_url, settings.weaviate_collection)
    if not class_name:
        logger.error("Could not determine Weaviate class name to update")
        return False
    logger.info(f"Using Weaviate class: {class_name}")
    logger.info("")

    # Stats
    stats = {
        "total_chunks": 0,
        "chunks_with_tags": 0,
        "chunks_without_tags": 0,
        "opensearch_updated": 0,
        "weaviate_updated": 0,
        "weaviate_failed": 0,
        "errors": 0,
    }

    # Per-doc cache: doc_id -> (exact_map, normalized_map, page_map)
    doc_text_id_cache: Dict[
        str, tuple[Dict[str, str], Dict[str, str], Dict[int, str]]
    ] = {}

    # Load and process chunks
    logger.info("Loading chunks...")

    updates_opensearch = []

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

                # Weaviate update (resolve UUID by doc_id+text)
                if not dry_run:
                    doc_id = chunk.get("doc_id")
                    text = chunk.get("text", "")
                    if not doc_id or not text:
                        logger.warning(
                            f"Line {line_num}: missing doc_id/text for chunk {chunk_id}, skipping Weaviate"
                        )
                    else:
                        # Build cache if needed
                        if doc_id not in doc_text_id_cache:
                            try:
                                doc_text_id_cache[doc_id] = _build_doc_text_id_map(
                                    weaviate_base_url, class_name, doc_id
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to build Weaviate map for doc_id={doc_id}: {e}"
                                )
                                stats["weaviate_failed"] += 1
                                # continue to next chunk
                                doc_text_id_cache[doc_id] = ({}, {}, {})

                        # Try multiple matching strategies
                        exact_map, normalized_map, page_map = doc_text_id_cache.get(
                            doc_id, ({}, {}, {})
                        )
                        uuid = None

                        # Strategy 1: Exact match
                        uuid = exact_map.get(text)

                        # Strategy 2: Normalized match
                        if not uuid:
                            normalized_text = _normalize_text(text)
                            uuid = normalized_map.get(normalized_text)

                        # Strategy 3: Page number match (if page exists in chunk metadata)
                        if not uuid:
                            page_num = chunk.get("metadata", {}).get("page")
                            if page_num is not None:
                                uuid = page_map.get(page_num)

                        if not uuid:
                            # Not found; skip with warning
                            logger.warning(
                                f"Weaviate uuid not found for chunk_id={chunk_id} (doc_id={doc_id}); text mismatch"
                            )
                            stats["weaviate_failed"] += 1
                        else:
                            # Patch object
                            try:
                                resp = requests.patch(
                                    f"{weaviate_base_url}/v1/objects/{class_name}/{uuid}",
                                    json={"properties": {"tags": tags}},
                                    headers={"Content-Type": "application/json"},
                                    timeout=20,
                                )
                                if resp.status_code in (200, 204):
                                    stats["weaviate_updated"] += 1
                                else:
                                    logger.warning(
                                        f"Weaviate update failed for {uuid} (chunk_id={chunk_id}): "
                                        f"{resp.status_code} {resp.text[:200]}"
                                    )
                                    stats["weaviate_failed"] += 1
                            except Exception as e:
                                logger.warning(
                                    f"Weaviate update exception for chunk_id={chunk_id}: {e}"
                                )
                                stats["weaviate_failed"] += 1

                # Batch OS update flush
                if len(updates_opensearch) >= batch_size:
                    if not dry_run:
                        # OpenSearch bulk update
                        success, errors = helpers.bulk(
                            opensearch_client,
                            updates_opensearch,
                            raise_on_error=False,
                        )
                        stats["opensearch_updated"] += success
                    updates_opensearch = []

            except json.JSONDecodeError as e:
                logger.error(f"Line {line_num}: JSON decode error: {e}")
                stats["errors"] += 1
            except Exception as e:
                logger.error(f"Line {line_num}: Processing error: {e}")
                stats["errors"] += 1

    # Process remaining OpenSearch updates
    if updates_opensearch and not dry_run:
        logger.info("Processing final OpenSearch batch...")
        success, errors = helpers.bulk(
            opensearch_client, updates_opensearch, raise_on_error=False
        )
        stats["opensearch_updated"] += success

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
        logger.info(f"Weaviate failed: {stats['weaviate_failed']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("")
        logger.info("✅ Backfill completed")
    else:
        logger.info("")
        logger.info("DRY RUN: No updates applied")
        logger.info(f"Would update {stats['chunks_with_tags']} chunks")

    logger.info("=" * 80)

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill tags using REST API")
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

    success = backfill_tags_restapi(
        chunks_file=args.chunks_file,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    sys.exit(0 if success else 1)
