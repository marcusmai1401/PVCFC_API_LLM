"""
Post-Ingestion Versioning Script

Creates version snapshots from existing ingestion outputs.
Useful for manually versioning past ingestions or when ingestion
was run without auto-versioning enabled.

Usage:
    python tools/ops/create_version.py --ingestion-dir artifacts/ingestion_production \
        --version-id v1.0 --description "Production baseline"
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from loguru import logger

from app.storage.manifest_writer import ManifestWriter
from app.storage.version_manager import VersionManager


def create_version_from_ingestion(
    ingestion_dir: Path,
    version_id: str,
    description: str = "",
    tags: list = None,
    base_dir: Path = None,
) -> bool:
    """
    Create a version snapshot from an ingestion directory.

    Args:
        ingestion_dir: Directory containing ingestion outputs
        version_id: Unique version identifier
        description: Human-readable description
        tags: Optional tags for categorization
        base_dir: Base artifacts directory (default: artifacts/)

    Returns:
        True if successful
    """
    logger.info("=" * 80)
    logger.info("POST-INGESTION VERSIONING")
    logger.info("=" * 80)

    ingestion_dir = Path(ingestion_dir)
    if not ingestion_dir.exists():
        logger.error(f"Ingestion directory not found: {ingestion_dir}")
        return False

    # Default base directory
    if base_dir is None:
        base_dir = PROJECT_ROOT / "artifacts"
    else:
        base_dir = Path(base_dir)

    logger.info(f"📁 Ingestion directory: {ingestion_dir}")
    logger.info(f"📦 Version ID: {version_id}")
    logger.info(f"📝 Description: {description or '(none)'}")
    logger.info(f"🏷️  Tags: {', '.join(tags) if tags else '(none)'}")
    logger.info("")

    # Check for required ingestion artifacts
    manifests_dir = ingestion_dir / "manifests"
    corpus_manifest = manifests_dir / "corpus.jsonl"
    chunks_jsonl = ingestion_dir / "chunks" / "chunks.jsonl"

    if not corpus_manifest.exists():
        logger.error(f"Corpus manifest not found: {corpus_manifest}")
        logger.info(
            "💡 Hint: Make sure you're pointing to the ingestion output directory"
        )
        return False

    if not chunks_jsonl.exists():
        logger.warning(f"Chunks JSONL not found: {chunks_jsonl}")
        logger.info("Continuing anyway (might be chunk JSON files instead)...")

    # Create or generate ingestion manifest for versioning
    ingestion_manifest_path = ingestion_dir / "manifest.json"

    if not ingestion_manifest_path.exists():
        logger.info("📝 Generating ingestion manifest from existing outputs...")
        ingestion_manifest = _generate_manifest_from_ingestion(ingestion_dir)

        if not ingestion_manifest:
            logger.error("Failed to generate manifest from ingestion outputs")
            return False

        # Write the manifest
        with open(ingestion_manifest_path, "w", encoding="utf-8") as f:
            json.dump(ingestion_manifest, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Generated manifest: {ingestion_manifest_path}")
    else:
        logger.info(f"📋 Using existing manifest: {ingestion_manifest_path}")

    # Initialize version manager
    vm = VersionManager(base_dir)

    # Check if version already exists
    existing = vm.get_version(version_id)
    if existing:
        logger.warning(f"⚠️  Version {version_id} already exists!")
        response = input("Overwrite? [y/N]: ")
        if response.lower() != "y":
            logger.info("Cancelled by user")
            return False

    # Create version snapshot
    try:
        version_meta = vm.create_version(
            version_id=version_id,
            ingestion_manifest_path=ingestion_manifest_path,
            index_manifest_path=None,  # No index yet
            description=description,
            tags=tags,
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ VERSION CREATED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Version ID: {version_meta['version_id']}")
        logger.info(f"Created at: {version_meta['created_at']}")
        logger.info(f"Total chunks: {version_meta['stats']['total_chunks']}")
        logger.info(f"Unique chunks: {version_meta['stats']['unique_chunks']}")
        logger.info("")
        logger.info(f"📦 Version directory: {base_dir / 'versions' / version_id}")
        logger.info("")

        return True

    except Exception as e:
        logger.error(f"Failed to create version: {e}", exc_info=True)
        return False


def _generate_manifest_from_ingestion(ingestion_dir: Path) -> dict:
    """
    Generate an ingestion manifest from existing ingestion outputs.

    Args:
        ingestion_dir: Directory containing ingestion outputs

    Returns:
        Manifest dictionary or None if failed
    """
    try:
        # Count chunks from corpus manifest
        corpus_manifest = ingestion_dir / "manifests" / "corpus.jsonl"
        total_docs = 0
        total_chunks = 0

        if corpus_manifest.exists():
            with open(corpus_manifest, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        total_docs += 1

        # Count chunks from chunks directory
        chunks_dir = ingestion_dir / "chunks"
        if chunks_dir.exists():
            # Try JSONL first
            chunks_jsonl = chunks_dir / "chunks.jsonl"
            if chunks_jsonl.exists():
                with open(chunks_jsonl, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            total_chunks += 1
            else:
                # Count individual chunk JSON files
                chunk_files = list(chunks_dir.glob("*_chunks.json"))
                for chunk_file in chunk_files:
                    with open(chunk_file, "r", encoding="utf-8") as f:
                        chunks = json.load(f)
                        total_chunks += len(chunks)

        # Generate ingestion ID from directory name or timestamp
        dir_name = ingestion_dir.name
        if dir_name.startswith("ingestion_"):
            ingestion_id = dir_name
        else:
            ingestion_id = (
                f"ingestion_{dir_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

        # Find artifacts (look for parquet, JSONL, etc.)
        artifacts = {}

        # Look for chunks parquet
        parquet_files = list(ingestion_dir.glob("**/*.parquet"))
        if parquet_files:
            artifacts["chunks_parquet"] = str(
                parquet_files[0].relative_to(ingestion_dir.parent)
            )
        elif chunks_jsonl := (ingestion_dir / "chunks" / "chunks.jsonl"):
            if chunks_jsonl.exists():
                artifacts["chunks_jsonl"] = str(
                    chunks_jsonl.relative_to(ingestion_dir.parent)
                )

        # Construct manifest
        manifest = {
            "version": "1.0.0",
            "ingestion_id": ingestion_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "config": {"source": "auto-detected", "chunk_strategy": "unknown"},
            "source": {
                "data_dir": "unknown",
                "total_files": total_docs,
                "processed_files": total_docs,
                "quarantined_files": 0,
            },
            "chunks": {
                "total_chunks": total_chunks,
                "unique_chunks": total_chunks,  # Can't determine from existing data
                "duplicate_chunks": 0,
                "avg_tokens_per_chunk": 0,
            },
            "embeddings": {
                "total_embedded": 0,
                "cache_hits": 0,
                "api_calls": 0,
                "total_cost_usd": 0.0,
            },
            "artifacts": artifacts,
            "lineage": {"parent_version": None, "incremental": False},
        }

        logger.info(f"📊 Detected: {total_docs} documents, {total_chunks} chunks")
        return manifest

    except Exception as e:
        logger.error(f"Failed to generate manifest: {e}", exc_info=True)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Create version snapshot from existing ingestion outputs"
    )

    parser.add_argument(
        "--ingestion-dir",
        type=Path,
        required=True,
        help="Directory containing ingestion outputs (e.g., artifacts/ingestion_production)",
    )

    parser.add_argument(
        "--version-id",
        type=str,
        required=True,
        help="Unique version identifier (e.g., 'v1.0', 'production_baseline')",
    )

    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Human-readable description of this version",
    )

    parser.add_argument(
        "--tags",
        type=str,
        nargs="+",
        default=None,
        help="Optional tags for categorization (e.g., production stable)",
    )

    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Base artifacts directory (default: artifacts/)",
    )

    args = parser.parse_args()

    # Validate ingestion directory
    if not args.ingestion_dir.exists():
        logger.error(f"Ingestion directory does not exist: {args.ingestion_dir}")
        logger.info("\n💡 Example usage:")
        logger.info("  python tools/ops/create_version.py \\")
        logger.info("      --ingestion-dir artifacts/ingestion_production \\")
        logger.info("      --version-id v1.0 \\")
        logger.info("      --description 'Production baseline with 150 PDFs'")
        sys.exit(1)

    # Create version
    success = create_version_from_ingestion(
        ingestion_dir=args.ingestion_dir,
        version_id=args.version_id,
        description=args.description,
        tags=args.tags,
        base_dir=args.base_dir,
    )

    if success:
        logger.info("🎉 Version creation complete!")
        sys.exit(0)
    else:
        logger.error("❌ Version creation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
