"""
Dependencies for loading and managing search indices.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import Settings
from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
    create_hybrid_modern_retriever,
)
from app.rag.retriever import HybridRetriever, create_hybrid_retriever
from app.rag.weaviate_retriever import WeaviateRetriever, create_weaviate_retriever

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages loading and access to search indices."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize index manager."""
        self.settings = settings or Settings()
        self.retriever = None
        self.metadata = {}
        self.retriever_type = None  # "hybrid_modern", "hybrid_legacy", or "weaviate"

    async def load_indices(self) -> Dict[str, Any]:
        """
        Load all required indices at startup.

        Mode selection logic:
        1. USE_HYBRID_MODERN=true  → Modern Hybrid (Weaviate + OpenSearch)
        2. USE_HYBRID_MODERN=false → Legacy Hybrid (FAISS + BM25 offline)

        Note: Weaviate-only mode removed for simplicity. Use modern hybrid
        if you only need Weaviate (OpenSearch will degrade gracefully).

        Returns:
            Dict with loaded components and metadata
        """
        logger.info("Loading search indices...")

        try:
            # Simple switch: Modern or Legacy
            if self.settings.use_hybrid_modern:
                logger.info("=" * 80)
                logger.info("MODERN HYBRID MODE - Weaviate + OpenSearch BM25")
                logger.info("=" * 80)
                return await self._load_hybrid_modern()
            else:
                logger.info("=" * 80)
                logger.info("LEGACY HYBRID MODE - FAISS + BM25 Offline")
                logger.info("=" * 80)
                return await self._load_hybrid_legacy()

        except Exception as e:
            logger.error(f"Failed to load indices: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "retriever_ready": False,
            }

    async def _load_hybrid_modern(self) -> Dict[str, Any]:
        """
        Load modern hybrid retriever (Weaviate + OpenSearch)

        Returns:
            Dict with load status and metadata
        """
        logger.info("Initializing Hybrid Modern Retriever...")

        try:
            # Create hybrid modern retriever
            self.retriever = create_hybrid_modern_retriever()
            self.retriever_type = "hybrid_modern"

            # Health check
            health = self.retriever.health_check()

            if health["overall_status"] == "critical":
                logger.error(f"Both Weaviate and OpenSearch are unhealthy: {health}")
                raise RuntimeError(
                    "Critical: Both Weaviate and OpenSearch failed health checks. "
                    "Set USE_HYBRID_MODERN=false to use legacy fallback."
                )

            if health["overall_status"] == "degraded":
                logger.warning(
                    f"Hybrid Modern running in degraded mode (one backend unhealthy): {health}"
                )

            # Get statistics
            stats = self.retriever.get_statistics()

            logger.info("Hybrid Modern Retriever loaded successfully")
            logger.info(f"  - Weaviate: {stats.get('weaviate', {}).get('status')}")
            logger.info(
                f"  - OpenSearch: {stats.get('opensearch', {}).get('num_documents', 'N/A')} docs"
            )

            return {
                "status": "loaded",
                "retriever_type": "hybrid_modern",
                "retriever_ready": True,
                "health": health,
                "statistics": stats,
                "metadata": {},
            }

        except Exception as e:
            logger.error(f"Failed to load Hybrid Modern retriever: {e}", exc_info=True)
            raise

    async def _load_weaviate_only(self) -> Dict[str, Any]:
        """
        Load Weaviate retriever (Phase 4)

        Returns:
            Dict with load status and metadata
        """
        logger.info("Initializing Weaviate retriever...")

        try:
            # Create Weaviate retriever
            self.retriever = create_weaviate_retriever(
                collection_name=self.settings.weaviate_collection,
            )
            self.retriever_type = "weaviate"

            # Perform health check
            health = self.retriever.health_check()

            if health["status"] == "healthy":
                logger.info(f"Weaviate retriever loaded successfully: {health}")
                return {
                    "status": "loaded",
                    "retriever_type": "weaviate",
                    "retriever_ready": True,
                    "weaviate_health": health,
                    "metadata": {},
                }
            else:
                logger.error(f"Weaviate health check failed: {health}")
                return {
                    "status": "error",
                    "error": health.get("error", "Unknown health check error"),
                    "retriever_type": "weaviate",
                    "retriever_ready": False,
                }

        except Exception as e:
            logger.error(f"Failed to load Weaviate retriever: {e}", exc_info=True)
            raise

    async def _load_hybrid_legacy(self) -> Dict[str, Any]:
        """
        Load legacy hybrid retriever (FAISS + BM25 offline)

        Returns:
            Dict with load status and metadata
        """
        logger.info("Initializing Legacy Hybrid Retriever (FAISS + BM25 offline)...")

        # Get project root path
        import app

        project_root = Path(app.__file__).parent.parent

        # Check if index directories exist (use absolute paths)
        # Use index directory from settings (configurable via INDEX_DIR env var)
        index_base = project_root / self.settings.index_dir
        bm25_path = index_base / "bm25"
        faiss_path = (
            index_base / "faiss_index"
            if "data/indexes" in self.settings.index_dir
            else index_base / "faiss"
        )

        bm25_exists = bm25_path.exists()
        faiss_exists = faiss_path.exists()

        if not bm25_exists:
            logger.warning(f"BM25 index not found at {bm25_path}")
        if not faiss_exists:
            logger.warning(f"FAISS index not found at {faiss_path}")

        # Create hybrid retriever using factory
        # It will handle loading indices internally
        self.retriever = create_hybrid_retriever(
            bm25_dir=str(bm25_path) if bm25_exists else None,
            faiss_dir=str(faiss_path) if faiss_exists else None,
        )
        self.retriever_type = "hybrid_legacy"  # Changed from "faiss" for consistency

        # Load metadata if available
        metadata_path = project_root / "artifacts" / "index" / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
            logger.info(f"Loaded index metadata: {self.metadata}")

        logger.info("All indices loaded successfully")

        # Get statistics from retriever
        stats = (
            self.retriever.get_statistics()
            if hasattr(self.retriever, "get_statistics")
            else {}
        )

        return {
            "status": "loaded",
            "retriever_type": "hybrid_legacy",
            "bm25_ready": bm25_exists,
            "faiss_ready": faiss_exists,
            "retriever_ready": self.retriever is not None,
            "metadata": self.metadata,
            "statistics": stats,
        }

    async def reload_indices(self) -> Dict[str, Any]:
        """
        Reload indices (e.g., after update).

        Returns:
            Reload status
        """
        logger.info("Reloading indices...")

        # Clear existing retriever
        self.retriever = None

        # Reload
        return await self.load_indices()

    def get_retriever(self) -> Optional[HybridRetriever]:
        """Get the hybrid retriever instance."""
        return self.retriever

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about loaded indices.

        Returns:
            Index statistics
        """
        # Return stats based on retriever type
        if self.retriever_type == "hybrid_modern":
            # Modern hybrid stats
            if self.retriever and hasattr(self.retriever, "get_statistics"):
                stats = self.retriever.get_statistics()
                return {
                    "retriever_type": "hybrid_modern",
                    "weaviate": stats.get("weaviate", {}),
                    "opensearch": stats.get("opensearch", {}),
                    "config": stats.get("config", {}),
                    "metadata": self.metadata,
                }
        elif self.retriever_type == "weaviate":
            # Weaviate stats
            health = self.retriever.health_check() if self.retriever else {}
            return {
                "retriever_type": "weaviate",
                "weaviate": {
                    "loaded": health.get("status") == "healthy",
                    "collection": self.settings.weaviate_collection,
                    "ready": health.get("ready", False),
                },
                "metadata": self.metadata,
            }
        elif self.retriever_type == "hybrid_legacy":
            # Legacy hybrid stats (FAISS + BM25 offline)
            if self.retriever and hasattr(self.retriever, "get_statistics"):
                raw_stats = self.retriever.get_statistics()

                # Transform to expected format
                bm25_count = raw_stats.get("bm25_documents", 0)
                faiss_count = raw_stats.get("faiss_documents", 0)

                return {
                    "retriever_type": "hybrid_legacy",
                    "bm25": {
                        "loaded": bm25_count > 0,
                        "doc_count": bm25_count,
                        "chunk_count": bm25_count,
                    },
                    "faiss": {
                        "loaded": faiss_count > 0,
                        "vector_count": faiss_count,
                        "dimension": 768,
                    },
                    "config": raw_stats.get("config", {}),
                    "metadata": self.metadata,
                }

        # Return basic stats if retriever not available
        return {
            "retriever_type": self.retriever_type or "unknown",
            "metadata": self.metadata,
        }


# Global index manager instance
_index_manager: Optional[IndexManager] = None


def get_index_manager(settings: Optional[Settings] = None) -> IndexManager:
    """
    Get or create the global index manager.

    Args:
        settings: Optional settings override

    Returns:
        IndexManager instance
    """
    global _index_manager

    if _index_manager is None:
        _index_manager = IndexManager(settings=settings)

    return _index_manager


async def startup_indices(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """
    Load indices during application startup.

    Args:
        settings: Optional settings override

    Returns:
        Load status
    """
    manager = get_index_manager(settings)
    return await manager.load_indices()


async def get_retriever_dependency():
    """
    FastAPI dependency for getting retriever.
    Returns either HybridRetriever (FAISS) or WeaviateRetriever based on config.

    Returns:
        Retriever instance (HybridRetriever or WeaviateRetriever)

    Raises:
        RuntimeError: If retriever not initialized
    """
    manager = get_index_manager()
    retriever = manager.get_retriever()

    if retriever is None:
        raise RuntimeError("Retriever not initialized. Indices may not be loaded.")

    return retriever
