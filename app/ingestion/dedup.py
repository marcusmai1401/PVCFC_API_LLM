"""
Content Deduplication Module

Provides hash-based deduplication to avoid redundant embedding computation.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)


class ContentDeduplicator:
    """
    Hash-based content deduplicator.

    Tracks seen content hashes to avoid redundant processing.
    """

    def __init__(self):
        """Initialize deduplicator"""
        self._seen_hashes: Set[str] = set()
        self.metrics = {
            "total_checked": 0,
            "duplicates_found": 0,
            "unique_content": 0,
        }

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """
        Compute content hash for text.

        Normalizes text before hashing to catch semantic duplicates.

        Args:
            text: Input text

        Returns:
            SHA256 hash (hex string)
        """
        # Normalize text
        normalized = text.lower().strip()
        # Normalize whitespace
        normalized = " ".join(normalized.split())

        # Compute hash
        hash_obj = hashlib.sha256(normalized.encode("utf-8"))
        return hash_obj.hexdigest()

    def is_duplicate(self, text: str) -> bool:
        """
        Check if text is a duplicate.

        Args:
            text: Input text

        Returns:
            True if duplicate, False if unique
        """
        self.metrics["total_checked"] += 1

        content_hash = self.compute_content_hash(text)

        if content_hash in self._seen_hashes:
            self.metrics["duplicates_found"] += 1
            logger.debug(f"Duplicate content found: {content_hash[:12]}...")
            return True

        self._seen_hashes.add(content_hash)
        self.metrics["unique_content"] += 1
        return False

    def get_hash(self, text: str) -> str:
        """
        Get content hash without marking as seen.

        Args:
            text: Input text

        Returns:
            Content hash
        """
        return self.compute_content_hash(text)

    def mark_as_seen(self, content_hash: str):
        """
        Mark a content hash as seen.

        Args:
            content_hash: Content hash to mark
        """
        self._seen_hashes.add(content_hash)

    def reset(self):
        """Reset deduplicator state"""
        self._seen_hashes.clear()
        self.metrics = {
            "total_checked": 0,
            "duplicates_found": 0,
            "unique_content": 0,
        }

    def get_metrics(self) -> dict:
        """Get deduplication metrics"""
        metrics = self.metrics.copy()

        if metrics["total_checked"] > 0:
            metrics["duplicate_rate"] = (
                metrics["duplicates_found"] / metrics["total_checked"]
            )
            metrics["unique_rate"] = (
                metrics["unique_content"] / metrics["total_checked"]
            )
        else:
            metrics["duplicate_rate"] = 0.0
            metrics["unique_rate"] = 0.0

        return metrics

    def __len__(self) -> int:
        """Return number of unique hashes seen"""
        return len(self._seen_hashes)


class PersistentDeduplicator(ContentDeduplicator):
    """
    Deduplicator with persistent storage.

    Stores seen hashes in a file for persistence across runs.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Initialize persistent deduplicator.

        Args:
            cache_file: Path to cache file (default: artifacts/dedup_cache.txt)
        """
        super().__init__()

        if cache_file is None:
            cache_file = Path("artifacts/ingestion/dedup_cache.txt")

        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing hashes
        self._load_cache()

    def _load_cache(self):
        """Load hashes from cache file"""
        if not self.cache_file.exists():
            logger.info(f"No existing dedup cache found at {self.cache_file}")
            return

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                for line in f:
                    hash_value = line.strip()
                    if hash_value:
                        self._seen_hashes.add(hash_value)

            logger.info(
                f"Loaded {len(self._seen_hashes)} hashes from cache: {self.cache_file}"
            )

        except Exception as e:
            logger.error(f"Failed to load dedup cache: {e}")

    def _save_cache(self):
        """Save hashes to cache file"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                for hash_value in sorted(self._seen_hashes):
                    f.write(f"{hash_value}\n")

            logger.info(
                f"Saved {len(self._seen_hashes)} hashes to cache: {self.cache_file}"
            )

        except Exception as e:
            logger.error(f"Failed to save dedup cache: {e}")

    def save(self):
        """Explicitly save cache to disk"""
        self._save_cache()

    def __del__(self):
        """Save cache on destruction"""
        try:
            self._save_cache()
        except:
            pass  # Don't raise exceptions in __del__
