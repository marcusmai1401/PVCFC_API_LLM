"""
Version-Aware Retriever

Loads and uses specific index versions for retrieval.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.indexers.bm25_indexer import BM25Indexer
from app.rag.indexers.faiss_indexer import VectorIndexer

from .version_manager import VersionManager

logger = logging.getLogger(__name__)


class VersionedRetriever:
    """
    Retriever that can load and use specific index versions.

    Features:
    - Load indices from specific versions
    - Hybrid retrieval (BM25 + FAISS)
    - Version switching without restarting
    """

    def __init__(
        self, base_dir: Path, version_id: Optional[str] = None, auto_load: bool = True
    ):
        """
        Initialize versioned retriever.

        Args:
            base_dir: Base artifacts directory
            version_id: Specific version to load (None = latest)
            auto_load: Automatically load indices on init
        """
        self.base_dir = Path(base_dir)
        self.version_manager = VersionManager(base_dir)

        self.current_version_id = None
        self.bm25_indexer = None
        self.vector_indexer = None

        if auto_load:
            if version_id:
                self.load_version(version_id)
            else:
                self.load_latest()

    def load_version(self, version_id: str) -> bool:
        """
        Load indices from a specific version.

        Args:
            version_id: Version to load

        Returns:
            True if successful
        """
        logger.info(f"Loading version: {version_id}")

        version = self.version_manager.get_version(version_id)
        if not version:
            logger.error(f"Version {version_id} not found")
            return False

        artifacts = version.get("artifacts", {})

        try:
            # Load BM25 index
            if "bm25_dir" in artifacts:
                bm25_dir = self.base_dir / artifacts["bm25_dir"]
                if bm25_dir.exists():
                    self.bm25_indexer = BM25Indexer()
                    self.bm25_indexer.load_index(str(bm25_dir))
                    logger.info(f"✅ Loaded BM25 index from version {version_id}")
                else:
                    logger.warning(f"BM25 index not found: {bm25_dir}")

            # Load FAISS index
            if "faiss_dir" in artifacts:
                faiss_dir = self.base_dir / artifacts["faiss_dir"]
                if faiss_dir.exists():
                    self.vector_indexer = VectorIndexer()
                    self.vector_indexer.load(str(faiss_dir))
                    logger.info(f"✅ Loaded FAISS index from version {version_id}")
                else:
                    logger.warning(f"FAISS index not found: {faiss_dir}")

            self.current_version_id = version_id
            logger.info(f"✅ Loaded version {version_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to load version {version_id}: {e}", exc_info=True)
            return False

    def load_latest(self) -> bool:
        """
        Load the latest version.

        Returns:
            True if successful
        """
        latest = self.version_manager.get_latest_version()
        if not latest:
            logger.error("No versions available")
            return False

        return self.load_version(latest["version_id"])

    def load_current(self) -> bool:
        """
        Load the current active version.

        Returns:
            True if successful
        """
        current = self.version_manager.get_current_version()
        if not current:
            logger.warning("No current version set, loading latest")
            return self.load_latest()

        return self.load_version(current)

    def search_bm25(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search using BM25 index.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of search results
        """
        if not self.bm25_indexer:
            logger.error("BM25 index not loaded")
            return []

        return self.bm25_indexer.search(query, top_k=top_k)

    def search_faiss(self, query_embedding, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search using FAISS index.

        Args:
            query_embedding: Query embedding vector (2D array)
            top_k: Number of results

        Returns:
            List of search results
        """
        if not self.vector_indexer:
            logger.error("FAISS index not loaded")
            return []

        search_results = self.vector_indexer.search(query_embedding, top_k=top_k)

        # Convert to standard format
        results = []
        for idx, score in search_results[0]:
            doc = self.vector_indexer.documents[idx]
            results.append({"text": doc.text, "score": score, "metadata": doc.metadata})

        return results

    def hybrid_search(
        self,
        query: str,
        query_embedding,
        top_k: int = 10,
        bm25_weight: float = 0.5,
        faiss_weight: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining BM25 and FAISS.

        Args:
            query: Search query text
            query_embedding: Query embedding vector
            top_k: Number of final results
            bm25_weight: Weight for BM25 scores
            faiss_weight: Weight for FAISS scores

        Returns:
            List of search results with combined scores
        """
        # Get results from both indices
        bm25_results = self.search_bm25(query, top_k=top_k * 2)
        faiss_results = self.search_faiss(query_embedding, top_k=top_k * 2)

        # Combine scores by chunk_id
        combined_scores = {}

        # Add BM25 scores
        for result in bm25_results:
            chunk_id = result.get("chunk_id")
            if chunk_id:
                combined_scores[chunk_id] = {
                    "text": result["text"],
                    "metadata": result,
                    "bm25_score": result["score"] * bm25_weight,
                    "faiss_score": 0.0,
                }

        # Add FAISS scores
        for result in faiss_results:
            chunk_id = result["metadata"].get("chunk_id")
            if chunk_id:
                if chunk_id in combined_scores:
                    combined_scores[chunk_id]["faiss_score"] = (
                        result["score"] * faiss_weight
                    )
                else:
                    combined_scores[chunk_id] = {
                        "text": result["text"],
                        "metadata": result["metadata"],
                        "bm25_score": 0.0,
                        "faiss_score": result["score"] * faiss_weight,
                    }

        # Calculate final scores and sort
        final_results = []
        for chunk_id, data in combined_scores.items():
            final_score = data["bm25_score"] + data["faiss_score"]
            final_results.append(
                {
                    "chunk_id": chunk_id,
                    "text": data["text"],
                    "metadata": data["metadata"],
                    "score": final_score,
                    "bm25_score": data["bm25_score"],
                    "faiss_score": data["faiss_score"],
                }
            )

        # Sort by combined score
        final_results.sort(key=lambda x: x["score"], reverse=True)

        return final_results[:top_k]

    def get_version_info(self) -> Dict[str, Any]:
        """
        Get information about currently loaded version.

        Returns:
            Version metadata
        """
        if not self.current_version_id:
            return {"error": "No version loaded"}

        version = self.version_manager.get_version(self.current_version_id)
        if not version:
            return {"error": "Current version not found in history"}

        return {
            "version_id": self.current_version_id,
            "created_at": version.get("created_at"),
            "description": version.get("description"),
            "stats": version.get("stats"),
            "bm25_loaded": self.bm25_indexer is not None,
            "faiss_loaded": self.vector_indexer is not None,
        }

    def list_available_versions(
        self, limit: Optional[int] = 10
    ) -> List[Dict[str, Any]]:
        """
        List available versions.

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of version metadata
        """
        return self.version_manager.list_versions(limit=limit)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    from pathlib import Path

    # Initialize retriever
    base_dir = Path("artifacts")
    retriever = VersionedRetriever(base_dir, auto_load=False)

    print(f"\n🔍 Versioned Retriever Test")
    print(f"Base directory: {retriever.base_dir}")

    # List available versions
    versions = retriever.list_available_versions()
    print(f"\n📋 Available versions: {len(versions)}")
    for v in versions:
        print(f"  - {v['version_id']}: {v.get('description', 'N/A')}")
        print(f"    Created: {v['created_at']}")
        print(f"    Chunks: {v['stats']['total_chunks']}")

    # Try to load latest
    if versions:
        print(f"\n⏳ Loading latest version...")
        success = retriever.load_latest()
        if success:
            info = retriever.get_version_info()
            print(f"\n✅ Loaded version: {info['version_id']}")
            print(f"   BM25 loaded: {info['bm25_loaded']}")
            print(f"   FAISS loaded: {info['faiss_loaded']}")
    else:
        print("\n⚠️  No versions available to load")
