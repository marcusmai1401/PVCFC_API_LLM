"""
Version Manager for Index Versioning

Manages version history, snapshots, and version-aware retrieval.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manifest_writer import ManifestWriter

logger = logging.getLogger(__name__)


class VersionManager:
    """
    Manages versioning for ingestion artifacts and indices.

    Features:
    - Create version snapshots
    - Track version history
    - Rollback to previous versions
    - Version-aware retrieval
    """

    def __init__(self, base_dir: Path):
        """
        Initialize version manager.

        Args:
            base_dir: Base artifacts directory (e.g., artifacts/)
        """
        self.base_dir = Path(base_dir)
        self.versions_dir = self.base_dir / "versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.versions_dir / "version_history.json"
        self.history = self._load_history()

        logger.info(f"VersionManager initialized: {self.base_dir}")

    def _load_history(self) -> Dict[str, Any]:
        """Load version history from file."""
        if not self.history_file.exists():
            return {
                "versions": [],
                "current_version": None,
                "created_at": datetime.utcnow().isoformat() + "Z",
            }

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load version history: {e}")
            return {"versions": [], "current_version": None}

    def _save_history(self):
        """Save version history to file."""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            logger.debug(
                f"Saved version history: {len(self.history['versions'])} versions"
            )
        except Exception as e:
            logger.error(f"Failed to save version history: {e}")

    def create_version(
        self,
        version_id: str,
        ingestion_manifest_path: Path,
        index_manifest_path: Optional[Path] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new version snapshot.

        Args:
            version_id: Unique version identifier (e.g., "v1", "20251002_150000")
            ingestion_manifest_path: Path to ingestion manifest
            index_manifest_path: Optional path to index manifest
            description: Human-readable description
            tags: Optional tags for categorization

        Returns:
            Version metadata dictionary
        """
        logger.info(f"Creating version snapshot: {version_id}")

        # Create version directory
        version_dir = self.versions_dir / version_id
        if version_dir.exists():
            logger.warning(f"Version {version_id} already exists, overwriting...")
            shutil.rmtree(version_dir)
        version_dir.mkdir(parents=True)

        # Load ingestion manifest
        ingestion_manifest = ManifestWriter.read_manifest(ingestion_manifest_path)

        # Copy artifacts to version directory
        artifacts = ingestion_manifest.get("artifacts", {})
        version_artifacts = {}

        # Copy chunks parquet
        chunks_parquet_str = artifacts.get("chunks_parquet", "")
        if chunks_parquet_str:
            chunks_parquet = Path(chunks_parquet_str)
            if chunks_parquet.exists():
                dest = version_dir / chunks_parquet.name
                shutil.copy2(chunks_parquet, dest)
                version_artifacts["chunks_parquet"] = str(
                    dest.relative_to(self.base_dir)
                )
                logger.debug(f"Copied chunks: {chunks_parquet.name}")

        # Copy ingestion manifest
        dest_manifest = version_dir / "manifest.json"
        shutil.copy2(ingestion_manifest_path, dest_manifest)
        version_artifacts["manifest"] = str(dest_manifest.relative_to(self.base_dir))

        # Copy index manifest if provided
        if index_manifest_path and index_manifest_path.exists():
            index_manifest = ManifestWriter.read_manifest(index_manifest_path)
            dest_index_manifest = version_dir / "index_manifest.json"
            shutil.copy2(index_manifest_path, dest_index_manifest)
            version_artifacts["index_manifest"] = str(
                dest_index_manifest.relative_to(self.base_dir)
            )

            # Copy BM25 index
            bm25_info = index_manifest.get("bm25", {})
            bm25_dir = Path(bm25_info.get("index_file", "")).parent
            if bm25_dir.exists():
                dest_bm25 = version_dir / "bm25"
                shutil.copytree(bm25_dir, dest_bm25)
                version_artifacts["bm25_dir"] = str(
                    dest_bm25.relative_to(self.base_dir)
                )
                logger.debug("Copied BM25 index")

            # Copy FAISS index
            faiss_info = index_manifest.get("faiss", {})
            faiss_dir = Path(faiss_info.get("index_file", "")).parent
            if faiss_dir.exists():
                dest_faiss = version_dir / "faiss"
                shutil.copytree(faiss_dir, dest_faiss)
                version_artifacts["faiss_dir"] = str(
                    dest_faiss.relative_to(self.base_dir)
                )
                logger.debug("Copied FAISS index")

        # Create version metadata
        version_meta = {
            "version_id": version_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "description": description,
            "tags": tags or [],
            "ingestion_id": ingestion_manifest.get("ingestion_id"),
            "artifacts": version_artifacts,
            "stats": {
                "total_chunks": ingestion_manifest.get("chunks", {}).get(
                    "total_chunks", 0
                ),
                "unique_chunks": ingestion_manifest.get("chunks", {}).get(
                    "unique_chunks", 0
                ),
                "total_embedded": ingestion_manifest.get("embeddings", {}).get(
                    "total_embedded", 0
                ),
            },
        }

        # Add to history
        self.history["versions"].append(version_meta)
        self.history["current_version"] = version_id
        self._save_history()

        logger.info(
            f"✅ Created version {version_id} with {version_meta['stats']['total_chunks']} chunks"
        )
        return version_meta

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific version.

        Args:
            version_id: Version identifier

        Returns:
            Version metadata or None if not found
        """
        for version in self.history["versions"]:
            if version["version_id"] == version_id:
                return version
        return None

    def list_versions(
        self, tags: Optional[List[str]] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List available versions.

        Args:
            tags: Optional filter by tags
            limit: Optional limit on number of results

        Returns:
            List of version metadata (newest first)
        """
        versions = self.history["versions"]

        # Filter by tags if provided
        if tags:
            versions = [
                v for v in versions if any(tag in v.get("tags", []) for tag in tags)
            ]

        # Sort by created_at (newest first)
        versions = sorted(versions, key=lambda v: v.get("created_at", ""), reverse=True)

        # Apply limit
        if limit:
            versions = versions[:limit]

        return versions

    def get_latest_version(self) -> Optional[Dict[str, Any]]:
        """Get the latest version."""
        versions = self.list_versions(limit=1)
        return versions[0] if versions else None

    def get_current_version(self) -> Optional[str]:
        """Get current active version ID."""
        return self.history.get("current_version")

    def set_current_version(self, version_id: str) -> bool:
        """
        Set the current active version (for rollback).

        Args:
            version_id: Version to activate

        Returns:
            True if successful
        """
        version = self.get_version(version_id)
        if not version:
            logger.error(f"Version {version_id} not found")
            return False

        self.history["current_version"] = version_id
        self._save_history()

        logger.info(f"✅ Set current version to: {version_id}")
        return True

    def rollback(
        self,
        version_id: str,
        target_ingestion_dir: Path,
        target_index_dir: Optional[Path] = None,
    ) -> bool:
        """
        Rollback to a previous version by restoring artifacts.

        Args:
            version_id: Version to rollback to
            target_ingestion_dir: Target directory for ingestion artifacts
            target_index_dir: Optional target directory for indices

        Returns:
            True if successful
        """
        logger.info(f"Rolling back to version: {version_id}")

        version = self.get_version(version_id)
        if not version:
            logger.error(f"Version {version_id} not found")
            return False

        version_dir = self.versions_dir / version_id
        if not version_dir.exists():
            logger.error(f"Version directory not found: {version_dir}")
            return False

        try:
            # Restore ingestion artifacts
            target_ingestion_dir = Path(target_ingestion_dir)
            target_ingestion_dir.mkdir(parents=True, exist_ok=True)

            artifacts = version["artifacts"]

            # Restore chunks parquet
            if "chunks_parquet" in artifacts:
                src = self.base_dir / artifacts["chunks_parquet"]
                if src.exists():
                    dest = target_ingestion_dir / src.name
                    shutil.copy2(src, dest)
                    logger.debug(f"Restored: {src.name}")

            # Restore manifest
            if "manifest" in artifacts:
                src = self.base_dir / artifacts["manifest"]
                if src.exists():
                    dest = target_ingestion_dir / "manifest.json"
                    shutil.copy2(src, dest)
                    logger.debug("Restored manifest")

            # Restore indices if target provided
            if target_index_dir:
                target_index_dir = Path(target_index_dir)
                target_index_dir.mkdir(parents=True, exist_ok=True)

                # Restore BM25
                if "bm25_dir" in artifacts:
                    src = self.base_dir / artifacts["bm25_dir"]
                    if src.exists():
                        dest = target_index_dir / "bm25"
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(src, dest)
                        logger.debug("Restored BM25 index")

                # Restore FAISS
                if "faiss_dir" in artifacts:
                    src = self.base_dir / artifacts["faiss_dir"]
                    if src.exists():
                        dest = target_index_dir / "faiss"
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(src, dest)
                        logger.debug("Restored FAISS index")

                # Restore index manifest
                if "index_manifest" in artifacts:
                    src = self.base_dir / artifacts["index_manifest"]
                    if src.exists():
                        dest = target_index_dir / "index_manifest.json"
                        shutil.copy2(src, dest)
                        logger.debug("Restored index manifest")

            # Update current version
            self.set_current_version(version_id)

            logger.info(f"✅ Rolled back to version {version_id}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            return False

    def compare_versions(self, version_id_1: str, version_id_2: str) -> Dict[str, Any]:
        """
        Compare two versions.

        Args:
            version_id_1: First version
            version_id_2: Second version

        Returns:
            Comparison dictionary
        """
        v1 = self.get_version(version_id_1)
        v2 = self.get_version(version_id_2)

        if not v1 or not v2:
            return {"error": "One or both versions not found"}

        stats1 = v1.get("stats", {})
        stats2 = v2.get("stats", {})

        comparison = {
            "version_1": {
                "id": version_id_1,
                "created_at": v1.get("created_at"),
                "stats": stats1,
            },
            "version_2": {
                "id": version_id_2,
                "created_at": v2.get("created_at"),
                "stats": stats2,
            },
            "diff": {
                "chunks_delta": stats2.get("total_chunks", 0)
                - stats1.get("total_chunks", 0),
                "unique_chunks_delta": stats2.get("unique_chunks", 0)
                - stats1.get("unique_chunks", 0),
                "embedded_delta": stats2.get("total_embedded", 0)
                - stats1.get("total_embedded", 0),
            },
        }

        return comparison

    def delete_version(self, version_id: str, force: bool = False) -> bool:
        """
        Delete a version snapshot.

        Args:
            version_id: Version to delete
            force: Allow deletion of current version

        Returns:
            True if successful
        """
        if version_id == self.history.get("current_version") and not force:
            logger.error(
                f"Cannot delete current version {version_id} without force=True"
            )
            return False

        version = self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found")
            return False

        # Remove from history
        self.history["versions"] = [
            v for v in self.history["versions"] if v["version_id"] != version_id
        ]

        # Remove directory
        version_dir = self.versions_dir / version_id
        if version_dir.exists():
            shutil.rmtree(version_dir)
            logger.debug(f"Removed version directory: {version_dir}")

        # Update current version if deleted
        if version_id == self.history.get("current_version"):
            latest = self.get_latest_version()
            self.history["current_version"] = latest["version_id"] if latest else None

        self._save_history()
        logger.info(f"✅ Deleted version {version_id}")
        return True


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    from pathlib import Path

    # Initialize version manager
    base_dir = Path("artifacts")
    vm = VersionManager(base_dir)

    print(f"\n📦 Version Manager Test")
    print(f"Base directory: {vm.base_dir}")
    print(f"Versions directory: {vm.versions_dir}")

    # List versions
    versions = vm.list_versions()
    print(f"\n📋 Available versions: {len(versions)}")
    for v in versions:
        print(f"  - {v['version_id']}: {v.get('description', 'N/A')}")
        print(f"    Created: {v['created_at']}")
        print(f"    Chunks: {v['stats']['total_chunks']}")

    # Get current version
    current = vm.get_current_version()
    print(f"\n✅ Current version: {current}")
