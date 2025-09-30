#!/usr/bin/env python
"""
Migration script to add 'page' field to existing BM25 and FAISS indices.
Ensures all chunks have consistent page metadata for citations.

Usage:
    python tools/migrate_page_metadata.py --bm25-dir artifacts/index/bm25
    python tools/migrate_page_metadata.py --faiss-dir artifacts/index/faiss
    python tools/migrate_page_metadata.py --bm25-dir artifacts/index/bm25 --faiss-dir artifacts/index/faiss
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Import page utilities
from app.utils.page_utils import extract_page_number, normalize_page_metadata


def backup_directory(dir_path: Path) -> Path:
    """Create backup of index directory before migration"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = dir_path.parent / f"{dir_path.name}_backup_{timestamp}"

    logger.info(f"Creating backup: {dir_path} -> {backup_path}")
    shutil.copytree(dir_path, backup_path)

    return backup_path


def migrate_bm25_index(index_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    """
    Migrate BM25 index to add page field to metadata

    Args:
        index_dir: Directory containing BM25 index
        dry_run: If True, only analyze without modifying

    Returns:
        Migration statistics
    """
    logger.info(f"Migrating BM25 index at {index_dir}")

    # Load metadata
    metadata_file = index_dir / "metadata.json"
    if not metadata_file.exists():
        logger.error(f"Metadata file not found: {metadata_file}")
        return {"status": "error", "message": "metadata.json not found"}

    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata_list = json.load(f)

    # Statistics
    stats = {
        "total_chunks": len(metadata_list),
        "already_has_page": 0,
        "added_from_page_start": 0,
        "added_from_page_nums": 0,
        "added_from_chunk_id": 0,
        "defaulted_to_1": 0,
        "modified": 0,
    }

    # Process each metadata entry
    modified_metadata = []
    for meta in metadata_list:
        original_page = meta.get("page")

        # Normalize metadata to ensure page field
        normalized_meta = normalize_page_metadata(meta.copy())

        # Track statistics
        if original_page is not None:
            stats["already_has_page"] += 1
        else:
            stats["modified"] += 1
            new_page = normalized_meta["page"]

            # Determine source of page number
            if meta.get("page_start") == new_page:
                stats["added_from_page_start"] += 1
            elif (
                "page_nums" in meta
                and meta["page_nums"]
                and meta["page_nums"][0] == new_page
            ):
                stats["added_from_page_nums"] += 1
            elif "chunk_id" in meta and f"page_{new_page}" in str(meta["chunk_id"]):
                stats["added_from_chunk_id"] += 1
            else:
                stats["defaulted_to_1"] += 1

        modified_metadata.append(normalized_meta)

    # Save if not dry run
    if not dry_run and stats["modified"] > 0:
        # Create backup first
        backup_path = backup_directory(index_dir)
        stats["backup_path"] = str(backup_path)

        # Save updated metadata
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(modified_metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Updated {stats['modified']} metadata entries")
    else:
        logger.info(f"Dry run: Would update {stats['modified']} entries")

    stats["status"] = "success"
    stats["dry_run"] = dry_run
    return stats


def migrate_faiss_index(index_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    """
    Migrate FAISS index to add page field to metadata

    Args:
        index_dir: Directory containing FAISS index
        dry_run: If True, only analyze without modifying

    Returns:
        Migration statistics
    """
    logger.info(f"Migrating FAISS index at {index_dir}")

    # Load metadata
    # Support both JSON and legacy PKL metadata files
    json_file = index_dir / "metadatas.json"
    pkl_file = index_dir / "metadatas.pkl"

    metadata_list = None
    metadata_source = None

    if json_file.exists():
        metadata_source = "json"
        with open(json_file, "r", encoding="utf-8") as f:
            metadata_list = json.load(f)
    elif pkl_file.exists():
        metadata_source = "pkl"
        import pickle

        with open(pkl_file, "rb") as f:
            metadata_list = pickle.load(f)
    else:
        logger.error(f"Metadata file not found: {json_file} or {pkl_file}")
        return {
            "status": "error",
            "message": "metadatas.json or metadatas.pkl not found",
        }

    # Statistics
    stats = {
        "total_chunks": len(metadata_list),
        "already_has_page": 0,
        "added_from_page_start": 0,
        "added_from_page_nums": 0,
        "added_from_chunk_id": 0,
        "defaulted_to_1": 0,
        "modified": 0,
    }

    # Process each metadata entry
    modified_metadata = []
    for meta in metadata_list:
        original_page = meta.get("page")

        # Normalize metadata to ensure page field
        normalized_meta = normalize_page_metadata(meta.copy())

        # Track statistics
        if original_page is not None:
            stats["already_has_page"] += 1
        else:
            stats["modified"] += 1
            new_page = normalized_meta["page"]

            # Determine source of page number
            if meta.get("page_start") == new_page:
                stats["added_from_page_start"] += 1
            elif (
                "page_nums" in meta
                and meta["page_nums"]
                and meta["page_nums"][0] == new_page
            ):
                stats["added_from_page_nums"] += 1
            elif "chunk_id" in meta and f"page_{new_page}" in str(meta["chunk_id"]):
                stats["added_from_chunk_id"] += 1
            else:
                stats["defaulted_to_1"] += 1

        modified_metadata.append(normalized_meta)

    # Save if not dry run
    if not dry_run and stats["modified"] > 0:
        # Create backup first
        backup_path = backup_directory(index_dir)
        stats["backup_path"] = str(backup_path)

        # Save updated metadata as JSON (preferred)
        with open(index_dir / "metadatas.json", "w", encoding="utf-8") as f:
            json.dump(modified_metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Updated {stats['modified']} metadata entries")
    else:
        logger.info(f"Dry run: Would update {stats['modified']} entries")

    stats["status"] = "success"
    stats["dry_run"] = dry_run
    return stats


def print_statistics(stats: Dict[str, Any], index_type: str):
    """Print migration statistics in a readable format"""
    print(f"\n{index_type} Migration Statistics:")
    print("=" * 50)

    if stats["status"] == "error":
        print(f"❌ Error: {stats.get('message', 'Unknown error')}")
        return

    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Already has page: {stats['already_has_page']}")
    print(f"Modified: {stats['modified']}")

    if stats["modified"] > 0:
        print("\nPage source breakdown:")
        print(f"  - From page_start: {stats['added_from_page_start']}")
        print(f"  - From page_nums: {stats['added_from_page_nums']}")
        print(f"  - From chunk_id: {stats['added_from_chunk_id']}")
        print(f"  - Defaulted to 1: {stats['defaulted_to_1']}")

    if stats.get("backup_path"):
        print(f"\n✅ Backup created: {stats['backup_path']}")

    if stats["dry_run"]:
        print("\n⚠️  Dry run - no changes were made")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate indices to add page metadata field"
    )
    parser.add_argument("--bm25-dir", type=str, help="Path to BM25 index directory")
    parser.add_argument("--faiss-dir", type=str, help="Path to FAISS index directory")
    parser.add_argument(
        "--dry-run", action="store_true", help="Analyze without making changes"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")

    # Check that at least one index is specified
    if not args.bm25_dir and not args.faiss_dir:
        parser.error("At least one of --bm25-dir or --faiss-dir must be specified")

    # Migrate BM25 index if specified
    if args.bm25_dir:
        bm25_dir = Path(args.bm25_dir)
        if not bm25_dir.exists():
            logger.error(f"BM25 directory not found: {bm25_dir}")
        else:
            stats = migrate_bm25_index(bm25_dir, dry_run=args.dry_run)
            print_statistics(stats, "BM25")

    # Migrate FAISS index if specified
    if args.faiss_dir:
        faiss_dir = Path(args.faiss_dir)
        if not faiss_dir.exists():
            logger.error(f"FAISS directory not found: {faiss_dir}")
        else:
            stats = migrate_faiss_index(faiss_dir, dry_run=args.dry_run)
            print_statistics(stats, "FAISS")

    print("\n✅ Migration complete!")


if __name__ == "__main__":
    main()
