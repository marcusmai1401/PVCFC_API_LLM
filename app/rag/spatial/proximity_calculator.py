"""
Proximity Calculator
Calculate spatial distances and alignment between tag components
"""
import math
from typing import List, Tuple

from app.rag.spatial.schemas import Component


class ProximityCalculator:
    """Calculate spatial relationships between components"""

    # Conversion factor: PDF points to millimeters
    # Standard: 1 inch = 72 points, 1 inch = 25.4mm
    # Therefore: 1 point = 25.4/72 ≈ 0.353 mm
    POINTS_TO_MM = 25.4 / 72

    def calculate_distance(self, comp1: Component, comp2: Component) -> float:
        """
        Calculate Euclidean distance between component centers (in mm)

        Args:
            comp1, comp2: Components to measure distance between

        Returns:
            Distance in millimeters
        """
        center1 = comp1.center
        center2 = comp2.center

        dx = center2[0] - center1[0]
        dy = center2[1] - center1[1]

        distance_points = math.sqrt(dx**2 + dy**2)
        distance_mm = distance_points * self.POINTS_TO_MM

        return distance_mm

    def calculate_max_distance(self, components: List[Component]) -> float:
        """
        Calculate maximum pairwise distance among components

        Args:
            components: List of components

        Returns:
            Maximum distance in mm
        """
        if len(components) < 2:
            return 0.0

        max_dist = 0.0
        for i, comp1 in enumerate(components):
            for comp2 in components[i + 1 :]:
                dist = self.calculate_distance(comp1, comp2)
                max_dist = max(max_dist, dist)

        return max_dist

    def check_vertical_alignment(
        self, comp1: Component, comp2: Component, tolerance_mm: float = 5.0
    ) -> bool:
        """
        Check if two components are vertically aligned (X coordinates similar)

        Args:
            comp1, comp2: Components to check
            tolerance_mm: Maximum X-axis difference in mm

        Returns:
            True if vertically aligned within tolerance
        """
        center1 = comp1.center
        center2 = comp2.center

        x_distance_points = abs(center2[0] - center1[0])
        x_distance_mm = x_distance_points * self.POINTS_TO_MM

        return x_distance_mm < tolerance_mm

    def check_horizontal_alignment(
        self, comp1: Component, comp2: Component, tolerance_mm: float = 5.0
    ) -> bool:
        """
        Check if two components are horizontally aligned (Y coordinates similar)

        Args:
            comp1, comp2: Components to check
            tolerance_mm: Maximum Y-axis difference in mm

        Returns:
            True if horizontally aligned within tolerance
        """
        center1 = comp1.center
        center2 = comp2.center

        y_distance_points = abs(center2[1] - center1[1])
        y_distance_mm = y_distance_points * self.POINTS_TO_MM

        return y_distance_mm < tolerance_mm

    def check_vertical_sequence(
        self,
        unit: Component,
        prefix: Component,
        suffix: Component,
        tolerance_mm: float = 2.0,
    ) -> bool:
        """
        Check if components are in correct vertical sequence (unit above prefix above suffix)

        Args:
            unit, prefix, suffix: Components to check
            tolerance_mm: Tolerance for ordering (allows slight misalignment)

        Returns:
            True if in correct sequence (top to bottom)
        """
        # Get Y centers (higher Y = lower on page in PDF coords)
        unit_y = unit.center[1]
        prefix_y = prefix.center[1]
        suffix_y = suffix.center[1]

        tolerance_points = tolerance_mm / self.POINTS_TO_MM

        # Check: unit above prefix (unit_y < prefix_y)
        # Allow small tolerance for slight misalignment
        unit_above_prefix = unit_y <= prefix_y + tolerance_points

        # Check: prefix above suffix
        prefix_above_suffix = prefix_y <= suffix_y + tolerance_points

        return unit_above_prefix and prefix_above_suffix

    def calculate_alignment_score(
        self, components: List[Component], tolerance_mm: float = 5.0
    ) -> float:
        """
        Calculate overall vertical alignment score for a group of components

        Returns:
            Score from 0.0 (not aligned) to 1.0 (perfectly aligned)
        """
        if len(components) < 2:
            return 1.0

        # Calculate average X coordinate
        avg_x = sum(c.center[0] for c in components) / len(components)

        # Calculate deviations from average
        deviations = []
        for comp in components:
            x_dev_points = abs(comp.center[0] - avg_x)
            x_dev_mm = x_dev_points * self.POINTS_TO_MM
            deviations.append(x_dev_mm)

        # Max deviation
        max_dev = max(deviations) if deviations else 0

        # Score: 1.0 if deviation = 0, decreases linearly to 0 at tolerance
        if max_dev == 0:
            return 1.0
        elif max_dev >= tolerance_mm:
            return 0.0
        else:
            return 1.0 - (max_dev / tolerance_mm)

    def merge_bboxes(self, components: List[Component]) -> List[float]:
        """
        Merge multiple component bboxes into a single encompassing bbox

        Args:
            components: List of components

        Returns:
            Merged bbox [x0, y0, x1, y1]
        """
        if not components:
            return [0, 0, 0, 0]

        x0 = min(c.bbox[0] for c in components)
        y0 = min(c.bbox[1] for c in components)
        x1 = max(c.bbox[2] for c in components)
        y1 = max(c.bbox[3] for c in components)

        return [x0, y0, x1, y1]

    def get_center(self, bbox: List[float]) -> Tuple[float, float]:
        """Get center point of a bbox"""
        return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
