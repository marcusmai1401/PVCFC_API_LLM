"""
Spatial Component Schemas
Data structures for spatial tag location system
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Component:
    """Individual tag component with spatial info"""

    text: str
    component_type: str  # "unit", "prefix", "suffix"
    bbox: List[float]  # [x0, y0, x1, y1]
    page: int
    doc_id: str
    span_id: Optional[int] = None

    @property
    def center(self) -> Tuple[float, float]:
        """Get bbox center point"""
        return ((self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2)


@dataclass
class TagCluster:
    """Spatial cluster of components forming a tag"""

    unit: Component
    prefix: Component
    suffix: Component
    score: float  # Cluster quality score (0-1)
    bbox: List[float]  # Merged bbox of all components
    page: int
    doc_id: str

    @property
    def tag_text(self) -> str:
        """Get full tag text"""
        return f"{self.unit.text} {self.prefix.text} {self.suffix.text}"


@dataclass
class SearchResult:
    """Search result from spatial or extraction search"""

    page: int
    doc_id: str
    score: float
    bbox: Optional[List[float]] = None
    source: str = "unknown"  # "spatial" or "extraction"
    metadata: Optional[dict] = None


@dataclass
class FusedResult:
    """Fused result from hybrid search"""

    page: int
    doc_id: str
    confidence: float  # Final confidence (0-1)
    verdict: str  # "BOTH_AGREE", "SPATIAL_ONLY", "EXTRACTION_ONLY"
    bbox: Optional[List[float]] = None
    spatial_score: float = 0.0
    extraction_score: float = 0.0


@dataclass
class LocationResult:
    """Final location result returned to user"""

    page: Optional[int] = None
    doc_id: Optional[str] = None
    confidence: Optional[float] = None
    bbox: Optional[List[float]] = None
    verdict: Optional[str] = None
    spatial_score: Optional[float] = None
    extraction_score: Optional[float] = None
    error: Optional[str] = None
    warning: Optional[str] = None


# OpenSearch index mapping
SPATIAL_INDEX_NAME = "pvcfc_pid_spatial_components"

SPATIAL_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "page": {"type": "integer"},
            "component": {"type": "keyword"},  # "04", "TXI", "2077"
            "component_type": {"type": "keyword"},  # "unit", "prefix", "suffix"
            "bbox": {
                "type": "object",
                "properties": {
                    "x0": {"type": "float"},
                    "y0": {"type": "float"},
                    "x1": {"type": "float"},
                    "y1": {"type": "float"},
                },
            },
            "center_x": {"type": "float"},
            "center_y": {"type": "float"},
            "span_id": {"type": "integer"},
        }
    },
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
}
