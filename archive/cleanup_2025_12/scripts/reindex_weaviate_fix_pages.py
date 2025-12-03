#!/usr/bin/env python
"""
Re-index Weaviate with Page Number Validation and Sanitation

Purpose:
- Fix page=0 or page=None issues in Weaviate
- Validate and sanitize all page numbers
- Re-index with clean data

Strategy:
1. Backup: Export current data to JSON
2. Validate: Check all pages, try to fix invalid ones
3. Re-index: Batch update with validated pages
4. Verify: Compare before/after statistics

Usage:
    python scripts/maintenance/reindex_weaviate_fix_pages.py --dry-run
    python scripts/maintenance/reindex_weaviate_fix_pages.py --execute
    python scripts/maintenance/reindex_weaviate_fix_pages.py --backup-only
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import weaviate
from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings

# Statistics
stats = {
    "total_chunks": 0,
    "page_none": 0,
    "page_zero": 0,
    "page_valid": 0,
    "fixed_from_metadata": 0,
    "fixed_from_content": 0,
    "fixed_from_chunk_id": 0,
    "fallback_to_one": 0,
    "failed_fixes": 0,
}


def extract_page_from_content(text: str) -> Optional[int]:
    """Extract page number from content markers"""
    if not text:
        return None

    # Look for <!-- Page N --> markers
    page_markers = re.findall(r"<!-- Page (\d+) -->", text)
    if page_markers:
        try:
            return int(page_markers[0])
        except (ValueError, TypeError):
            pass

    # Look for TABLE START markers with page info
    table_markers = re.findall(r"TABLE START \(Page (\d+)", text)
    if table_markers:
        try:
            return int(table_markers[0])
        except (ValueError, TypeError):
            pass

    return None


def extract_page_from_chunk_id(chunk_id: str) -> Optional[int]:
    """Extract page number from chunk_id patterns"""
    if not chunk_id:
        return None

    # Pattern: _p13_ or _p13 or p13_
    m = re.search(r"[_\-]p(\d+)[_\-]", chunk_id, flags=re.IGNORECASE)
    if not m:
        # Pattern: p13 at end
        m = re.search(r"p(\d+)$", chunk_id, flags=re.IGNORECASE)

    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            pass

    return None


def sanitize_page(
    page: Optional[int], chunk_id: str, text: str, metadata: Dict[str, Any]
) -> int:
    """Sanitize and validate page number with fallback strategies"""

    # Already valid
    if isinstance(page, int) and page > 0:
        stats["page_valid"] += 1
        return page

    # Track issue
    if page is None:
        stats["page_none"] += 1
    elif page == 0:
        stats["page_zero"] += 1

    logger.debug(f"Fixing page for chunk: {chunk_id[:50]}...")

    # Strategy 1: Check metadata
    meta_page = metadata.get("page") if metadata else None
    if isinstance(meta_page, int) and meta_page > 0:
        logger.debug(f"  ✓ Fixed from metadata: {meta_page}")
        stats["fixed_from_metadata"] += 1
        return meta_page

    # Strategy 2: Extract from content markers
    content_page = extract_page_from_content(text)
    if content_page:
        logger.debug(f"  ✓ Fixed from content marker: {content_page}")
        stats["fixed_from_content"] += 1
        return content_page

    # Strategy 3: Extract from chunk_id
    chunk_id_page = extract_page_from_chunk_id(chunk_id)
    if chunk_id_page:
        logger.debug(f"  ✓ Fixed from chunk_id: {chunk_id_page}")
        stats["fixed_from_chunk_id"] += 1
        return chunk_id_page

    # Fallback: Use 1 (safer than 0/None)
    logger.warning(f"  ⚠️ No page found, using fallback=1 for: {chunk_id[:50]}")
    stats["fallback_to_one"] += 1
    return 1


def backup_weaviate_data(client: weaviate.WeaviateClient, collection_name: str) -> Path:
    """Backup current Weaviate data to JSON"""
    logger.info("=" * 80)
    logger.info("BACKUP: Exporting Weaviate data...")
    logger.info("=" * 80)

    backup_dir = PROJECT_ROOT / "artifacts" / "backups" / "weaviate"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"weaviate_backup_{timestamp}.json"

    collection = client.collections.get(collection_name)

    # Fetch all objects
    logger.info(f"Fetching all objects from collection: {collection_name}")

    all_objects = []
    cursor = None
    batch_size = 100

    while True:
        if cursor:
            response = collection.query.fetch_objects(
                limit=batch_size,
                after=cursor,
                return_properties=[
                    "text",
                    "doc_id",
                    "page",
                    "tags",
                    "equipment_id",
                    "source_path",
                ],
            )
        else:
            response = collection.query.fetch_objects(
                limit=batch_size,
                return_properties=[
                    "text",
                    "doc_id",
                    "page",
                    "tags",
                    "equipment_id",
                    "source_path",
                ],
            )

        if not response.objects:
            break

        for obj in response.objects:
            all_objects.append(
                {
                    "uuid": str(obj.uuid),
                    "properties": obj.properties,
                }
            )

        logger.info(f"  Fetched {len(all_objects)} objects...")

        # Check if more results
        if len(response.objects) < batch_size:
            break

        cursor = response.objects[-1].uuid

    # Save to file
    logger.info(f"Saving backup to: {backup_file}")
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "collection": collection_name,
                "total_objects": len(all_objects),
                "objects": all_objects,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.success(f"✅ Backup complete: {len(all_objects)} objects saved")
    logger.info(f"   File: {backup_file}")

    return backup_file


def analyze_pages(objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze page number distribution"""
    logger.info("=" * 80)
    logger.info("ANALYSIS: Page number distribution")
    logger.info("=" * 80)

    analysis = {
        "total": len(objects),
        "page_none": 0,
        "page_zero": 0,
        "page_valid": 0,
        "page_distribution": {},
    }

    for obj in objects:
        props = obj.get("properties", {})
        page = props.get("page")

        if page is None:
            analysis["page_none"] += 1
        elif page == 0:
            analysis["page_zero"] += 1
        else:
            analysis["page_valid"] += 1
            # Track distribution
            page_range = f"{(page//10)*10}-{(page//10)*10+9}"
            analysis["page_distribution"][page_range] = (
                analysis["page_distribution"].get(page_range, 0) + 1
            )

    # Print analysis
    logger.info(f"Total objects: {analysis['total']}")
    logger.info(
        f"  Page = None: {analysis['page_none']} ({analysis['page_none']/analysis['total']*100:.1f}%)"
    )
    logger.info(
        f"  Page = 0: {analysis['page_zero']} ({analysis['page_zero']/analysis['total']*100:.1f}%)"
    )
    logger.info(
        f"  Page > 0: {analysis['page_valid']} ({analysis['page_valid']/analysis['total']*100:.1f}%)"
    )

    if analysis["page_none"] > 0 or analysis["page_zero"] > 0:
        logger.warning(
            f"⚠️  Found {analysis['page_none'] + analysis['page_zero']} objects with invalid pages"
        )

    return analysis


def validate_and_fix_pages(
    objects: List[Dict[str, Any]], dry_run: bool = True
) -> List[Dict[str, Any]]:
    """Validate and fix page numbers for all objects"""
    logger.info("=" * 80)
    logger.info(f"VALIDATION: {'DRY RUN' if dry_run else 'FIXING'} page numbers")
    logger.info("=" * 80)

    fixed_objects = []

    for i, obj in enumerate(objects):
        if (i + 1) % 100 == 0:
            logger.info(f"  Processing {i+1}/{len(objects)}...")

        props = obj.get("properties", {})
        original_page = props.get("page")

        # Sanitize page
        # Use doc_id + source_path as chunk identifier since chunk_id doesn't exist
        chunk_identifier = f"{props.get('doc_id', '')}:{props.get('source_path', '')}"
        fixed_page = sanitize_page(
            page=original_page,
            chunk_id=chunk_identifier,
            text=props.get("text", ""),
            metadata={},  # Weaviate doesn't have nested metadata in properties
        )

        # Update if changed
        if fixed_page != original_page:
            props["page"] = fixed_page
            obj["properties"] = props
            obj["page_changed"] = True
        else:
            obj["page_changed"] = False

        fixed_objects.append(obj)

    logger.info("=" * 80)
    logger.info("VALIDATION STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Total chunks: {stats['total_chunks']}")
    logger.info(f"  Page = None: {stats['page_none']}")
    logger.info(f"  Page = 0: {stats['page_zero']}")
    logger.info(f"  Page > 0 (valid): {stats['page_valid']}")
    logger.info("")
    logger.info(f"Fixes applied:")
    logger.info(f"  From metadata: {stats['fixed_from_metadata']}")
    logger.info(f"  From content markers: {stats['fixed_from_content']}")
    logger.info(f"  From chunk_id: {stats['fixed_from_chunk_id']}")
    logger.info(f"  Fallback to 1: {stats['fallback_to_one']}")

    changed_count = sum(1 for obj in fixed_objects if obj.get("page_changed"))
    logger.info("")
    logger.success(f"✅ {changed_count} objects will be updated")

    return fixed_objects


def reindex_weaviate(
    client: weaviate.WeaviateClient,
    collection_name: str,
    fixed_objects: List[Dict[str, Any]],
    dry_run: bool = True,
) -> bool:
    """Re-index Weaviate with fixed page numbers"""
    logger.info("=" * 80)
    logger.info(f"RE-INDEX: {'DRY RUN' if dry_run else 'EXECUTING'}")
    logger.info("=" * 80)

    if dry_run:
        logger.warning("🔍 DRY RUN MODE - No changes will be made")
        return True

    collection = client.collections.get(collection_name)

    # Batch update
    logger.info("Starting batch update...")

    updated = 0
    failed = 0

    # Process in batches
    batch_size = 100
    for i in range(0, len(fixed_objects), batch_size):
        batch = fixed_objects[i : i + batch_size]

        try:
            # Update each object
            with collection.batch.fixed_size(batch_size=batch_size) as batch_context:
                for obj in batch:
                    if not obj.get("page_changed"):
                        continue

                    # Update object with new page
                    batch_context.add_object(
                        properties=obj["properties"],
                        uuid=obj["uuid"],
                    )
                    updated += 1

            logger.info(f"  Batch {i//batch_size + 1}: {updated} objects updated")

        except Exception as e:
            logger.error(f"  Batch {i//batch_size + 1} failed: {e}")
            failed += len(batch)

    logger.info("=" * 80)
    logger.success(f"✅ Re-index complete: {updated} updated, {failed} failed")

    return failed == 0


def verify_reindex(client: weaviate.WeaviateClient, collection_name: str):
    """Verify re-index results"""
    logger.info("=" * 80)
    logger.info("VERIFICATION: Checking re-indexed data")
    logger.info("=" * 80)

    collection = client.collections.get(collection_name)

    # Count invalid pages
    try:
        # Check for page=0
        response = collection.aggregate.over_all(
            filters=weaviate.classes.query.Filter.by_property("page").equal(0)
        )
        page_zero_count = (
            response.total_count if hasattr(response, "total_count") else 0
        )

        logger.info(f"  Page = 0: {page_zero_count}")

        if page_zero_count == 0:
            logger.success("✅ No page=0 found!")
        else:
            logger.warning(f"⚠️  Still have {page_zero_count} objects with page=0")

    except Exception as e:
        logger.warning(f"Could not verify page=0 count: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Re-index Weaviate with page validation"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Analyze only, don't update"
    )
    parser.add_argument("--execute", action="store_true", help="Execute re-indexing")
    parser.add_argument("--backup-only", action="store_true", help="Only create backup")
    parser.add_argument(
        "--no-backup", action="store_true", help="Skip backup (not recommended)"
    )

    args = parser.parse_args()

    # Validate args
    if not args.dry_run and not args.execute and not args.backup_only:
        logger.warning(
            "No action specified. Use --dry-run, --execute, or --backup-only"
        )
        logger.info("Running in dry-run mode by default...")
        args.dry_run = True

    logger.info("=" * 80)
    logger.info("WEAVIATE PAGE NUMBER RE-INDEX")
    logger.info("=" * 80)
    logger.info(
        f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE' if args.execute else 'BACKUP ONLY'}"
    )
    logger.info(f"Collection: {settings.weaviate_collection}")
    logger.info("")

    try:
        # Connect to Weaviate
        logger.info("Connecting to Weaviate...")
        client = weaviate.connect_to_local(
            host=settings.weaviate_host,
            port=settings.weaviate_port,
        )

        collection_name = settings.weaviate_collection

        # Step 1: Backup (unless --no-backup)
        if not args.no_backup:
            backup_file = backup_weaviate_data(client, collection_name)
            logger.info("")

        if args.backup_only:
            logger.success("✅ Backup complete. Exiting.")
            return 0

        # Load backup for analysis
        logger.info("Loading data for analysis...")
        collection = client.collections.get(collection_name)

        # Fetch all objects
        all_objects = []
        cursor = None
        batch_size = 100

        while True:
            if cursor:
                response = collection.query.fetch_objects(
                    limit=batch_size,
                    after=cursor,
                    return_properties=[
                        "text",
                        "doc_id",
                        "page",
                        "tags",
                        "equipment_id",
                        "source_path",
                    ],
                )
            else:
                response = collection.query.fetch_objects(
                    limit=batch_size,
                    return_properties=[
                        "text",
                        "doc_id",
                        "page",
                        "tags",
                        "equipment_id",
                        "source_path",
                    ],
                )

            if not response.objects:
                break

            for obj in response.objects:
                all_objects.append(
                    {
                        "uuid": str(obj.uuid),
                        "properties": obj.properties,
                    }
                )

            if len(response.objects) < batch_size:
                break

            cursor = response.objects[-1].uuid

        stats["total_chunks"] = len(all_objects)

        # Step 2: Analyze
        analysis = analyze_pages(all_objects)
        logger.info("")

        # Step 3: Validate and fix
        fixed_objects = validate_and_fix_pages(all_objects, dry_run=args.dry_run)
        logger.info("")

        # Step 4: Re-index (if not dry-run)
        if args.execute:
            success = reindex_weaviate(
                client, collection_name, fixed_objects, dry_run=False
            )
            logger.info("")

            # Step 5: Verify
            if success:
                verify_reindex(client, collection_name)

        logger.info("=" * 80)
        logger.success("✅ Script complete!")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"❌ Script failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return 1

    finally:
        if "client" in locals():
            client.close()


if __name__ == "__main__":
    sys.exit(main())
