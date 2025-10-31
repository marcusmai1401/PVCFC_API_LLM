"""
Hybrid Fusion Engine
Combine spatial and extraction search results with voting
"""
from collections import defaultdict
from typing import List

from loguru import logger

from app.rag.spatial.schemas import FusedResult, SearchResult


class HybridFusionEngine:
    """Fuse spatial and extraction search results"""

    def __init__(
        self,
        spatial_weight: float = 0.4,
        extraction_weight: float = 0.6,
        agreement_bonus: float = 0.15,
    ):
        """
        Initialize fusion engine

        Args:
            spatial_weight: Weight for spatial search scores
            extraction_weight: Weight for extraction search scores
            agreement_bonus: Bonus when both methods agree on same page
        """
        self.spatial_weight = spatial_weight
        self.extraction_weight = extraction_weight
        self.agreement_bonus = agreement_bonus

    def fuse(
        self,
        spatial_results: List[SearchResult],
        extraction_results: List[SearchResult],
    ) -> List[FusedResult]:
        """
        Combine results from both methods with voting

        Args:
            spatial_results: Results from spatial search
            extraction_results: Results from extraction search

        Returns:
            Fused results sorted by confidence
        """
        logger.debug(
            f"Fusing: {len(spatial_results)} spatial + "
            f"{len(extraction_results)} extraction results"
        )

        # Build voting map: page -> {scores, bboxes, sources}
        page_votes = defaultdict(
            lambda: {
                "spatial_score": 0.0,
                "extraction_score": 0.0,
                "spatial_bbox": None,
                "extraction_bbox": None,
                "sources": [],
            }
        )

        # Collect spatial votes
        for result in spatial_results:
            page = result.page
            page_votes[page]["spatial_score"] = result.score
            page_votes[page]["spatial_bbox"] = result.bbox
            page_votes[page]["sources"].append("spatial")

        # Collect extraction votes
        for result in extraction_results:
            page = result.page
            page_votes[page]["extraction_score"] = result.score
            page_votes[page]["extraction_bbox"] = result.bbox
            page_votes[page]["sources"].append("extraction")

        # Calculate fused confidence for each page
        fused_results = []

        for page, votes in page_votes.items():
            result = self._calculate_fused_confidence(page, votes)
            fused_results.append(result)

        # Sort by confidence (highest first)
        fused_results.sort(key=lambda r: r.confidence, reverse=True)

        logger.info(
            f"Fusion complete: {len(fused_results)} fused results, "
            f"top confidence: {fused_results[0].confidence:.3f if fused_results else 0}"
        )

        return fused_results

    def _calculate_fused_confidence(self, page: int, votes: dict) -> FusedResult:
        """
        Calculate final confidence score for a page

        Confidence calculation:
        - Both agree: weighted sum + agreement bonus (0.95-0.99)
        - Spatial only: spatial_score * 0.75 (penalty for no confirmation)
        - Extraction only: extraction_score * 0.80 (penalty for no confirmation)
        """
        sources = votes["sources"]
        spatial_score = votes["spatial_score"]
        extraction_score = votes["extraction_score"]

        if len(sources) == 2:
            # BOTH methods agree on this page
            confidence = (
                spatial_score * self.spatial_weight
                + extraction_score * self.extraction_weight
                + self.agreement_bonus
            )
            confidence = min(0.99, confidence)  # Cap at 0.99
            verdict = "BOTH_AGREE"
            bbox = votes["spatial_bbox"]  # Prefer spatial bbox (more precise)

            logger.debug(
                f"Page {page}: BOTH_AGREE "
                f"(spatial={spatial_score:.2f}, extraction={extraction_score:.2f}) "
                f"→ confidence={confidence:.3f}"
            )

        elif "spatial" in sources:
            # SPATIAL only
            confidence = spatial_score * 0.75  # Penalty
            verdict = "SPATIAL_ONLY"
            bbox = votes["spatial_bbox"]

            logger.debug(
                f"Page {page}: SPATIAL_ONLY "
                f"(score={spatial_score:.2f}) → confidence={confidence:.3f}"
            )

        else:
            # EXTRACTION only
            confidence = extraction_score * 0.80  # Penalty
            verdict = "EXTRACTION_ONLY"
            bbox = votes["extraction_bbox"]

            logger.debug(
                f"Page {page}: EXTRACTION_ONLY "
                f"(score={extraction_score:.2f}) → confidence={confidence:.3f}"
            )

        return FusedResult(
            page=page,
            doc_id="Ammonia",  # TODO: Get from results
            confidence=confidence,
            verdict=verdict,
            bbox=bbox,
            spatial_score=spatial_score,
            extraction_score=extraction_score,
        )
