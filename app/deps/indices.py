"""
Dependencies for loading and managing search indices.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import Settings
from app.rag.retriever import HybridRetriever, create_hybrid_retriever

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages loading and access to search indices."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize index manager."""
        self.settings = settings or Settings()
        self.retriever = None
        self.metadata = {}

    async def load_indices(self) -> Dict[str, Any]:
        """
        Load all required indices at startup.

        Returns:
            Dict with loaded components and metadata
        """
        logger.info("Loading search indices...")

        try:
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
                "bm25_ready": bm25_exists,
                "faiss_ready": faiss_exists,
                "retriever_ready": self.retriever is not None,
                "metadata": self.metadata,
                "statistics": stats,
            }

        except Exception as e:
            logger.error(f"Failed to load indices: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "bm25_ready": False,
                "faiss_ready": False,
                "retriever_ready": False,
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
        # Get stats from retriever if available
        if self.retriever and hasattr(self.retriever, "get_statistics"):
            raw_stats = self.retriever.get_statistics()

            # Transform to expected format
            bm25_count = raw_stats.get("bm25_documents", 0)
            faiss_count = raw_stats.get("faiss_documents", 0)

            return {
                "bm25": {
                    "loaded": bm25_count > 0,
                    "doc_count": bm25_count,
                    "chunk_count": bm25_count,  # For BM25, doc_count = chunk_count
                },
                "faiss": {
                    "loaded": faiss_count > 0,
                    "vector_count": faiss_count,
                    "dimension": 768,  # Gemini embedding dimension
                },
                "config": raw_stats.get("config", {}),
                "metadata": self.metadata,
            }

        # Return basic stats if retriever not available
        return {
            "bm25": {"loaded": False, "doc_count": 0, "chunk_count": 0},
            "faiss": {"loaded": False, "vector_count": 0, "dimension": 0},
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


async def get_retriever_dependency() -> HybridRetriever:
    """
    FastAPI dependency for getting retriever.

    Returns:
        HybridRetriever instance

    Raises:
        RuntimeError: If retriever not initialized
    """
    manager = get_index_manager()
    retriever = manager.get_retriever()

    if retriever is None:
        raise RuntimeError("Retriever not initialized. Indices may not be loaded.")

    return retriever
