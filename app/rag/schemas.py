"""
Pydantic schemas for RAG API requests and responses.
Phase 2 implementation.
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============= REQUEST SCHEMAS =============


class AskRequest(BaseModel):
    """Request schema for /ask endpoint."""

    query: str = Field(..., min_length=1, description="User query in natural language")
    filters: Optional[Dict[str, List[str]]] = Field(
        default=None, description="Optional filters for doc_category or doc_id"
    )
    hyde: bool = Field(default=True, description="Enable HyDE expansion")
    max_context: int = Field(default=8, ge=1, le=20, description="Max context chunks")
    language: Literal["vi", "en"] = Field(default="vi", description="Response language")
    execution_mode: Literal["production", "heavy_only", "light_only"] = Field(
        default="production", description="LLM execution mode"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Áp suất vận hành tối đa của KT06101?",
                "filters": {
                    "doc_category": ["datasheet", "om"],
                    "doc_id": ["PVCFC-KT06101-datasheet-v1"],
                },
                "hyde": True,
                "max_context": 8,
                "language": "vi",
            }
        }
    )


class LocateRequest(BaseModel):
    """Request schema for /locate endpoint."""

    query: str = Field(..., description="Entity/symbol/text to locate")
    filters: Optional[Dict[str, List[str]]] = Field(
        default=None, description="Optional filters for doc_category or doc_id"
    )
    max_hits: int = Field(default=10, ge=1, le=50, description="Maximum hits to return")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "KT06101",
                "filters": {"doc_category": ["pid"], "doc_id": ["PVCFC-PID-04000-v1"]},
                "max_hits": 10,
            }
        }
    )


class ReportRequest(BaseModel):
    """Request schema for /report endpoint."""

    topic: str = Field(..., description="Main topic for the report")
    sub_queries: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Sub-queries to answer in the report",
    )
    format: Literal["markdown", "json"] = Field(
        default="markdown", description="Output format"
    )
    filters: Optional[Dict[str, List[str]]] = Field(
        default=None, description="Optional filters for doc_category or doc_id"
    )
    language: Literal["vi", "en"] = Field(default="vi", description="Response language")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "Thông số vận hành chính KT06101",
                "sub_queries": [
                    "Áp suất vận hành tối đa là bao nhiêu?",
                    "Nhiệt độ vận hành cho phép?",
                    "Các cảnh báo an toàn cần lưu ý?",
                ],
                "format": "markdown",
                "language": "vi",
            }
        }
    )


# ============= RESPONSE SCHEMAS =============


class Citation(BaseModel):
    """Citation information for a source."""

    doc_id: str = Field(..., description="Document identifier")
    page: int = Field(..., description="Page number")
    bbox: Optional[List[float]] = Field(
        default=None, description="Bounding box [x0, y0, x1, y1] if available"
    )
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Confidence score"
    )


class AskResponse(BaseModel):
    """Response schema for /ask endpoint."""

    answer: str = Field(..., description="Generated answer with citations")
    citations: List[Citation] = Field(..., description="Source citations")
    context_used: List[str] = Field(..., description="Chunk IDs used in context")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")
    meta: Dict[str, Any] = Field(..., description="Metadata (latency, model, k, etc.)")
    warnings: Optional[List[str]] = Field(
        default=None, description="Any warnings or degraded mode indicators"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "Theo tài liệu, áp suất vận hành tối đa của KT06101 là 10 bar...",
                "citations": [
                    {
                        "doc_id": "PVCFC-KT06101-datasheet-v1",
                        "page": 12,
                        "bbox": [100, 220, 380, 270],
                        "confidence": 0.95,
                    }
                ],
                "context_used": ["chunk_123", "chunk_456"],
                "confidence": 0.92,
                "meta": {
                    "latency_ms": 2300,
                    "model": "gemini-2.5-pro",
                    "k": 8,
                    "execution_mode": "production",
                },
            }
        }
    )


class LocationHit(BaseModel):
    """Single location hit for /locate endpoint."""

    doc_id: str = Field(..., description="Document identifier")
    page: int = Field(..., description="Page number")
    bbox: Optional[List[float]] = Field(
        default=None, description="Bounding box [x0, y0, x1, y1] if available"
    )
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    snippet: str = Field(..., description="Text snippet around the match")
    chunk_id: Optional[str] = Field(default=None, description="Source chunk ID")


class LocateResponse(BaseModel):
    """Response schema for /locate endpoint."""

    hits: List[LocationHit] = Field(..., description="Located positions")
    total_found: int = Field(..., ge=0, description="Total matches found")
    meta: Dict[str, Any] = Field(
        ..., description="Metadata (latency, search method, etc.)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hits": [
                    {
                        "doc_id": "PVCFC-PID-04000-v1",
                        "page": 3,
                        "bbox": [812, 450, 905, 490],
                        "score": 0.92,
                        "snippet": "...connected to KT06101 valve...",
                        "chunk_id": "chunk_789",
                    }
                ],
                "total_found": 3,
                "meta": {"latency_ms": 450, "search_method": "hybrid"},
            }
        }
    )


class ReportSection(BaseModel):
    """Single section of a report."""

    heading: str = Field(..., description="Section heading")
    content: str = Field(..., description="Section content")
    citations: List[Citation] = Field(..., description="Section citations")
    sub_query: Optional[str] = Field(
        default=None, description="Original sub-query for this section"
    )


class ReportResponse(BaseModel):
    """Response schema for /report endpoint."""

    title: str = Field(..., description="Report title")
    sections: List[ReportSection] = Field(..., description="Report sections")
    summary: Optional[str] = Field(default=None, description="Executive summary")
    meta: Dict[str, Any] = Field(
        ..., description="Metadata (total latency, models used, etc.)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Báo cáo tóm tắt KT06101",
                "sections": [
                    {
                        "heading": "Áp suất vận hành",
                        "content": "Áp suất vận hành tối đa cho phép là 10 bar...",
                        "citations": [
                            {
                                "doc_id": "PVCFC-KT06101-datasheet-v1",
                                "page": 12,
                                "confidence": 0.95,
                            }
                        ],
                        "sub_query": "Áp suất vận hành tối đa là bao nhiêu?",
                    }
                ],
                "summary": "KT06101 là thiết bị quan trọng với các thông số...",
                "meta": {
                    "total_latency_ms": 5400,
                    "sections_count": 3,
                    "total_citations": 8,
                },
            }
        }
    )


# ============= ERROR SCHEMAS =============


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error details"
    )
    trace_id: Optional[str] = Field(
        default=None, description="Request trace ID for debugging"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "message": "Invalid filters format",
                "details": {
                    "field": "filters.doc_category",
                    "reason": "Must be a list of strings",
                },
                "trace_id": "abc123-def456",
            }
        }
    )


# ============= INTERNAL SCHEMAS =============


class QueryTransformResult(BaseModel):
    """Result from query transformation."""

    normalized_query: str
    intent: Literal["qa", "locate", "report", "explain", "unknown"]
    hyde_queries: Optional[List[str]] = None
    filters: Optional[Dict[str, List[str]]] = None


class RetrievalResult(BaseModel):
    """Result from retrieval step."""

    chunks: List[Dict[str, Any]]
    scores: List[float]
    method: str  # "bm25", "faiss", "hybrid"
    expanded: bool = False


class RerankResult(BaseModel):
    """Result from reranking step."""

    chunks: List[Dict[str, Any]]
    scores: List[float]
    original_ranks: List[int]
    rerank_model: str


class CoVeCheckpoint(BaseModel):
    """Checkpoint for Chain-of-Verification."""

    claim: str
    check_query: str
    evidence_found: bool
    confidence: float
    supporting_chunks: List[str]
