"""
Component Clusterer
Find spatial clusters of components that form valid tags
"""
from typing import List

from loguru import logger

from app.rag.spatial.proximity_calculator import ProximityCalculator
from app.rag.spatial.schemas import Component, TagCluster


class ComponentClusterer:
    """Find spatial clusters of unit/prefix/suffix components forming tags"""

    def __init__(
        self,
        max_distance_mm: float = 25.0,
        alignment_tolerance_mm: float = 5.0,
        min_cluster_score: float = 0.6,
    ):
        """
        Initialize clusterer with spatial parameters

        Args:
            max_distance_mm: Maximum distance between components to form cluster
            alignment_tolerance_mm: Tolerance for vertical alignment
            min_cluster_score: Minimum quality score to accept cluster
        """
        self.max_distance_mm = max_distance_mm
        self.alignment_tolerance_mm = alignment_tolerance_mm
        self.min_cluster_score = min_cluster_score
        self.calc = ProximityCalculator()

    def find_tag_clusters(
        self,
        units: List[Component],
        prefixes: List[Component],
        suffixes: List[Component],
    ) -> List[TagCluster]:
        """
        Find all valid (unit, prefix, suffix) triplets forming tags

        Args:
            units: List of unit components (e.g., "04")
            prefixes: List of prefix components (e.g., "TXI")
            suffixes: List of suffix components (e.g., "2077")

        Returns:
            List of TagCluster objects with scores
        """
        clusters = []

        logger.debug(
            f"Finding clusters: {len(units)} units × {len(prefixes)} prefixes × "
            f"{len(suffixes)} suffixes = {len(units) * len(prefixes) * len(suffixes)} "
            f"possible combinations"
        )

        # Try all combinations
        for unit in units:
            for prefix in prefixes:
                for suffix in suffixes:
                    # Check if this triplet forms a valid cluster
                    cluster = self._evaluate_triplet(unit, prefix, suffix)

                    if cluster and cluster.score >= self.min_cluster_score:
                        clusters.append(cluster)

        # Sort by score (highest first)
        clusters.sort(key=lambda c: c.score, reverse=True)

        logger.info(
            f"Found {len(clusters)} valid clusters "
            f"(min_score={self.min_cluster_score:.2f})"
        )

        return clusters

    def _evaluate_triplet(
        self, unit: Component, prefix: Component, suffix: Component
    ) -> TagCluster:
        """
        Evaluate if three components form a valid tag cluster

        Returns:
            TagCluster if valid (score > threshold), None otherwise
        """
        # Calculate pairwise distances
        d_up = self.calc.calculate_distance(unit, prefix)
        d_ps = self.calc.calculate_distance(prefix, suffix)
        d_us = self.calc.calculate_distance(unit, suffix)

        max_dist = max(d_up, d_ps, d_us)

        # Reject if any component too far
        if max_dist > self.max_distance_mm:
            return None

        # Check vertical alignment
        aligned_up = self.calc.check_vertical_alignment(
            unit, prefix, self.alignment_tolerance_mm
        )
        aligned_ps = self.calc.check_vertical_alignment(
            prefix, suffix, self.alignment_tolerance_mm
        )
        aligned = aligned_up and aligned_ps

        # Check vertical sequence (unit above prefix above suffix)
        sequence_ok = self.calc.check_vertical_sequence(
            unit, prefix, suffix, tolerance_mm=2.0
        )

        # Calculate quality score
        score = self._calculate_cluster_score(
            max_dist, aligned, sequence_ok, [unit, prefix, suffix]
        )

        if score < self.min_cluster_score:
            return None

        # Create cluster
        merged_bbox = self.calc.merge_bboxes([unit, prefix, suffix])

        cluster = TagCluster(
            unit=unit,
            prefix=prefix,
            suffix=suffix,
            score=score,
            bbox=merged_bbox,
            page=unit.page,
            doc_id=unit.doc_id,
        )

        return cluster

    def _calculate_cluster_score(
        self,
        max_distance: float,
        aligned: bool,
        sequence_ok: bool,
        components: List[Component],
    ) -> float:
        """
        Calculate cluster quality score (0.0 to 1.0)

        Scoring factors:
        - Proximity: Closer components = higher score
        - Alignment: Vertically aligned = higher score
        - Sequence: Correct order (top-to-bottom) = higher score
        """
        # Proximity score (1.0 if distance=0, 0.0 if distance=max_threshold)
        proximity_score = max(0.0, 1.0 - (max_distance / self.max_distance_mm))

        # Alignment score (calculated based on deviation)
        alignment_score = self.calc.calculate_alignment_score(
            components, tolerance_mm=self.alignment_tolerance_mm
        )

        # Sequence score (1.0 if correct, 0.7 if not)
        sequence_score = 1.0 if sequence_ok else 0.7

        # Weighted combination
        total_score = (
            proximity_score * 0.4 + alignment_score * 0.3 + sequence_score * 0.3
        )

        return total_score

    def filter_overlapping_clusters(
        self, clusters: List[TagCluster], overlap_threshold: float = 0.5
    ) -> List[TagCluster]:
        """
        Filter out overlapping clusters, keeping highest scored ones

        Args:
            clusters: List of clusters (should be sorted by score)
            overlap_threshold: Minimum overlap ratio to consider overlapping

        Returns:
            Filtered list with no significant overlaps
        """
        if not clusters:
            return []

        filtered = []
        used_components = set()

        for cluster in clusters:
            # Check if any component already used
            comp_ids = {
                (cluster.unit.text, cluster.unit.span_id),
                (cluster.prefix.text, cluster.prefix.span_id),
                (cluster.suffix.text, cluster.suffix.span_id),
            }

            if not comp_ids.intersection(used_components):
                # No overlap, accept this cluster
                filtered.append(cluster)
                used_components.update(comp_ids)

        logger.debug(
            f"Filtered {len(clusters)} → {len(filtered)} clusters "
            f"(removed {len(clusters) - len(filtered)} overlaps)"
        )

        return filtered
