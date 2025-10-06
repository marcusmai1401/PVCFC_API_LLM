"""
Manifest Writer for Ingestion Lineage

Writes JSON manifests tracking ingestion configuration, metrics, and lineage.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ManifestWriter:
    """
    Writes ingestion manifests in JSON format for lineage tracking.
    """

    def __init__(self, output_path: Path):
        """
        Initialize manifest writer.

        Args:
            output_path: Path to manifest JSON file
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"ManifestWriter initialized: {self.output_path}")

    def write_ingestion_manifest(
        self,
        ingestion_id: str,
        config: Dict[str, Any],
        source_stats: Dict[str, Any],
        chunk_stats: Dict[str, Any],
        embedding_stats: Dict[str, Any],
        artifacts: Dict[str, str],
        lineage: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
    ) -> Dict[str, Any]:
        """
        Write ingestion manifest.

        Args:
            ingestion_id: Unique ingestion identifier
            config: Ingestion configuration (chunk size, model, etc.)
            source_stats: Source document statistics
            chunk_stats: Chunk generation statistics
            embedding_stats: Embedding generation statistics
            artifacts: Paths to generated artifacts
            lineage: Parent version and incremental info
            version: Manifest schema version

        Returns:
            Complete manifest dictionary
        """
        manifest = {
            "version": version,
            "ingestion_id": ingestion_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "config": config,
            "source": source_stats,
            "chunks": chunk_stats,
            "embeddings": embedding_stats,
            "artifacts": artifacts,
            "lineage": lineage or {"parent_version": None, "incremental": False},
        }

        # Write to file
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Wrote ingestion manifest: {self.output_path}")
        return manifest

    def write_index_manifest(
        self,
        index_id: str,
        source_ingestion: str,
        bm25_info: Dict[str, Any],
        faiss_info: Dict[str, Any],
        version: str = "1.0.0",
    ) -> Dict[str, Any]:
        """
        Write index manifest.

        Args:
            index_id: Unique index identifier
            source_ingestion: ID of source ingestion
            bm25_info: BM25 index metadata
            faiss_info: FAISS index metadata
            version: Manifest schema version

        Returns:
            Complete manifest dictionary
        """
        manifest = {
            "version": version,
            "index_id": index_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "source_ingestion": source_ingestion,
            "bm25": bm25_info,
            "faiss": faiss_info,
        }

        # Write to file
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Wrote index manifest: {self.output_path}")
        return manifest

    @staticmethod
    def read_manifest(manifest_path: Path) -> Dict[str, Any]:
        """
        Read manifest from file.

        Args:
            manifest_path: Path to manifest JSON

        Returns:
            Manifest dictionary
        """
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def get_latest_version(
        artifacts_dir: Path, prefix: str = "manifest_v"
    ) -> Optional[str]:
        """
        Get the latest version from manifest files in directory.

        Args:
            artifacts_dir: Directory containing manifest files
            prefix: Filename prefix to search for

        Returns:
            Latest version string or None
        """
        manifests = list(artifacts_dir.glob(f"{prefix}*.json"))
        if not manifests:
            return None

        # Sort by modification time
        latest = max(manifests, key=lambda p: p.stat().st_mtime)

        # Parse ingestion_id from manifest
        manifest = ManifestWriter.read_manifest(latest)
        return manifest.get("ingestion_id")


class IngestionTracker:
    """
    Utility to track ingestion metrics during processing.
    """

    def __init__(self):
        self.source_files = 0
        self.processed_files = 0
        self.quarantined_files = 0

        self.total_chunks = 0
        self.unique_chunks = 0
        self.duplicate_chunks = 0
        self.total_tokens = 0

        self.total_embedded = 0
        self.cache_hits = 0
        self.api_calls = 0
        self.total_cost_usd = 0.0

    def add_source_file(self, processed: bool = True):
        """Track a source file."""
        self.source_files += 1
        if processed:
            self.processed_files += 1
        else:
            self.quarantined_files += 1

    def add_chunks(self, count: int, tokens: int, unique: bool = True):
        """Track generated chunks."""
        self.total_chunks += count
        self.total_tokens += tokens
        if unique:
            self.unique_chunks += count
        else:
            self.duplicate_chunks += count

    def add_embeddings(self, count: int, cached: int, cost: float):
        """Track embedding generation."""
        self.total_embedded += count
        self.cache_hits += cached
        self.api_calls += count - cached
        self.total_cost_usd += cost

    def get_source_stats(self, data_dir: str) -> Dict[str, Any]:
        """Get source statistics."""
        return {
            "data_dir": data_dir,
            "total_files": self.source_files,
            "processed_files": self.processed_files,
            "quarantined_files": self.quarantined_files,
        }

    def get_chunk_stats(self) -> Dict[str, Any]:
        """Get chunk statistics."""
        avg_tokens = (
            (self.total_tokens / self.total_chunks) if self.total_chunks > 0 else 0
        )
        return {
            "total_chunks": self.total_chunks,
            "unique_chunks": self.unique_chunks,
            "duplicate_chunks": self.duplicate_chunks,
            "avg_tokens_per_chunk": round(avg_tokens, 1),
        }

    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding statistics."""
        return {
            "total_embedded": self.total_embedded,
            "cache_hits": self.cache_hits,
            "api_calls": self.api_calls,
            "total_cost_usd": round(self.total_cost_usd, 2),
        }


if __name__ == "__main__":
    # Quick sanity test
    logging.basicConfig(level=logging.INFO)

    # Create tracker
    tracker = IngestionTracker()
    tracker.add_source_file(processed=True)
    tracker.add_chunks(count=100, tokens=85000, unique=True)
    tracker.add_chunks(count=20, tokens=17000, unique=False)
    tracker.add_embeddings(count=100, cached=20, cost=0.02)

    # Create manifest
    output_path = Path("artifacts/test_manifest/manifest.json")
    writer = ManifestWriter(output_path)

    manifest = writer.write_ingestion_manifest(
        ingestion_id="test_ingest_20251002",
        config={
            "chunk_size": 900,
            "chunk_overlap": 140,
            "embedding_model": "gemini-embedding-001",
            "embedding_dim": 768,
            "dedup_enabled": True,
        },
        source_stats=tracker.get_source_stats("D:\\Data_Raw"),
        chunk_stats=tracker.get_chunk_stats(),
        embedding_stats=tracker.get_embedding_stats(),
        artifacts={
            "chunks_parquet": "artifacts/ingestion/chunks_v1.parquet",
            "manifest": "artifacts/ingestion/manifest_v1.json",
        },
    )

    print("\n📋 Generated Manifest:")
    print(json.dumps(manifest, indent=2))

    # Read back
    read_manifest = ManifestWriter.read_manifest(output_path)
    print(f"\n✅ Read manifest: ingestion_id = {read_manifest['ingestion_id']}")
