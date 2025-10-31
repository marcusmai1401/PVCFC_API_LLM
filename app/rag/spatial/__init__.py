"""
Spatial Tag Location Module
Component-based spatial proximity search for P&ID tags
"""
from app.rag.spatial.component_extractor import SpatialComponentExtractor
from app.rag.spatial.component_indexer import SpatialComponentIndexer
from app.rag.spatial.schemas import (
    SPATIAL_INDEX_MAPPING,
    SPATIAL_INDEX_NAME,
    Component,
    FusedResult,
    LocationResult,
    SearchResult,
    TagCluster,
)

__all__ = [
    "Component",
    "TagCluster",
    "SearchResult",
    "FusedResult",
    "LocationResult",
    "SPATIAL_INDEX_NAME",
    "SPATIAL_INDEX_MAPPING",
    "SpatialComponentExtractor",
    "SpatialComponentIndexer",
]
