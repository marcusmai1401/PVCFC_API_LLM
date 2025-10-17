"""
Tag Entity Schemas
Pydantic models for extracted tags

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 6.5
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class TagParts(BaseModel):
    """Component parts of a tag"""

    area: Optional[str] = None  # e.g., "04"
    code: str  # e.g., "PSAL" (required)
    num: str  # e.g., "2207" (required)
    suffix: Optional[str] = None  # e.g., "A/B", "2oo3", "-201B"


class TagEntity(BaseModel):
    """Extracted tag entity with bbox and metadata"""

    doc_id: str
    page: int  # 1-based
    tag: str  # Full tag text (e.g., "04 PSAL 2207")
    parts: TagParts
    bbox: List[float]  # [x0, y0, x1, y1] in page coordinates
    rotation: float = 0.0  # Rotation in degrees
    confidence: float = Field(ge=0.0, le=1.0)  # Normalized from scoring
    evidence_span_ids: List[int] = Field(default_factory=list)  # Span IDs used
    has_suffix: bool = False
    crop_path: Optional[str] = None  # Relative path to crop PNG
