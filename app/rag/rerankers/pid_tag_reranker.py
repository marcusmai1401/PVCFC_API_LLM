"""
P&ID Tag Reranker Module

Reranks retrieval results based on equipment tag presence and proximity to parameters
"""

from typing import Dict, List

from loguru import logger
from rapidfuzz import fuzz


class PIDTagReranker:
    """
    Rerank results based on tag presence and proximity to parameters

    Features:
    - Exact tag match boosting (metadata + text)
    - Fuzzy tag matching with RapidFuzz
    - Tag-parameter proximity detection
    - Configurable boost factors
    """

    def __init__(
        self,
        boost_meta_exact: float = 10.0,
        boost_text_exact: float = 5.0,
        boost_proximity: float = 3.0,
        fuzzy_threshold: int = 90,
        proximity_window: int = 100,
    ):
        """
        Initialize PID tag reranker

        Args:
            boost_meta_exact: Boost factor for exact tag in metadata (default: 10x)
            boost_text_exact: Boost factor for exact tag in text (default: 5x)
            boost_proximity: Boost factor for tag-parameter proximity (default: 3x)
            fuzzy_threshold: Minimum similarity for fuzzy match (default: 90%)
            proximity_window: Character window for proximity check (default: 100)
        """
        self.boost_meta_exact = boost_meta_exact
        self.boost_text_exact = boost_text_exact
        self.boost_proximity = boost_proximity
        self.fuzzy_threshold = fuzzy_threshold
        self.proximity_window = proximity_window

        # Parameter keywords for proximity detection
        self.param_keywords = [
            "pressure",
            "áp suất",
            "bar",
            "psi",
            "mpa",
            "kpa",
            "temperature",
            "nhiệt độ",
            "°c",
            "°f",
            "flow",
            "lưu lượng",
            "kg/h",
            "m³/h",
            "m3/h",
            "rate",
            "tốc độ",
        ]

        logger.info(
            f"PIDTagReranker initialized: "
            f"boost_meta={boost_meta_exact}, boost_text={boost_text_exact}, "
            f"boost_prox={boost_proximity}, fuzzy_threshold={fuzzy_threshold}"
        )

    def rerank(
        self, results: List[Dict], query_tags: List[str], top_k: int = 10
    ) -> List[Dict]:
        """
        Boost results based on exact/fuzzy tag matches

        Boost priority:
        1. Exact tag in metadata.tags (10x)
        2. Exact tag in text (5x)
        3. Fuzzy tag match (2-3x based on similarity)
        4. Tag + parameter proximity (3x)

        Args:
            results: List of retrieval results
            query_tags: Detected equipment tags from query
            top_k: Number of results to return

        Returns:
            Reranked results sorted by final score
        """
        if not results:
            return []

        if not query_tags:
            logger.debug("No query tags provided, returning original results")
            return results[:top_k]

        logger.info(f"Reranking {len(results)} results for tags: {query_tags}")

        reranked = []

        for result in results:
            score = result.get("score", 0.0)
            boosts = []

            text = result.get("text", "")
            metadata = result.get("metadata", {})

            # Boost 1: Exact tag in metadata.tags (highest priority)
            chunk_tags = metadata.get("tags", [])
            if chunk_tags:
                exact_matches = set(query_tags) & set(chunk_tags)
                if exact_matches:
                    boost = self.boost_meta_exact
                    score *= boost
                    boosts.append(f"meta_exact:{boost}")
                    logger.debug(
                        f"Chunk {metadata.get('chunk_id', 'unknown')}: "
                        f"exact metadata tag match {exact_matches}"
                    )

            # Boost 2: Exact tag in text
            for tag in query_tags:
                if tag.upper() in text.upper():
                    boost = self.boost_text_exact
                    score *= boost
                    boosts.append(f"text_exact:{boost}")
                    logger.debug(
                        f"Chunk {metadata.get('chunk_id', 'unknown')}: "
                        f"exact text match for {tag}"
                    )
                    break  # Only boost once for text match

            # Boost 3: Fuzzy tag match (only if no exact match)
            if not boosts:
                best_fuzzy_score = 0
                best_tag = None

                for tag in query_tags:
                    fuzzy_score = fuzz.partial_ratio(tag.upper(), text.upper())

                    if fuzzy_score > best_fuzzy_score:
                        best_fuzzy_score = fuzzy_score
                        best_tag = tag

                if best_fuzzy_score >= self.fuzzy_threshold:
                    # Boost proportional to similarity: 90% → 1.0x, 100% → 2.0x
                    boost = 1.0 + (best_fuzzy_score - self.fuzzy_threshold) / 100
                    score *= boost
                    boosts.append(f"fuzzy:{boost:.2f}@{best_fuzzy_score}%")
                    logger.debug(
                        f"Chunk {metadata.get('chunk_id', 'unknown')}: "
                        f"fuzzy match {best_tag} @ {best_fuzzy_score}%"
                    )

            # Boost 4: Tag + parameter proximity
            if self._has_tag_param_proximity(text, query_tags):
                boost = self.boost_proximity
                score *= boost
                boosts.append(f"proximity:{boost}")
                logger.debug(
                    f"Chunk {metadata.get('chunk_id', 'unknown')}: "
                    f"tag-parameter proximity detected"
                )

            result["final_score"] = score
            result["boosts"] = boosts
            reranked.append(result)

        # Sort by final score
        reranked.sort(key=lambda r: r["final_score"], reverse=True)

        if reranked:
            logger.info(
                f"PID reranking complete: top result boosted by {reranked[0]['boosts']}, "
                f"final_score={reranked[0]['final_score']:.4f}"
            )

        return reranked[:top_k]

    def _has_tag_param_proximity(self, text: str, tags: List[str]) -> bool:
        """
        Check if tags appear near parameters (within proximity window)

        Args:
            text: Chunk text
            tags: Equipment tags to check

        Returns:
            True if any tag is near a parameter keyword
        """
        for tag in tags:
            tag_pos = text.upper().find(tag.upper())
            if tag_pos == -1:
                continue

            # Extract window around tag
            window_start = max(0, tag_pos - self.proximity_window)
            window_end = min(len(text), tag_pos + len(tag) + self.proximity_window)
            window = text[window_start:window_end].lower()

            # Check for parameters in window
            if any(kw in window for kw in self.param_keywords):
                logger.debug(
                    f"Tag {tag} found near parameter in window: "
                    f"{window[max(0, tag_pos-window_start-20):tag_pos-window_start+len(tag)+20]}"
                )
                return True

        return False


# Export main class
__all__ = ["PIDTagReranker"]
