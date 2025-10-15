"""FastAPI application for Page-First RAG Agent

Provides REST API endpoints for question answering with citations.

Endpoints:
- POST /api/v1/ask - Ask a question
- GET /api/v1/health - Health check
- GET /api/v1/metrics - System metrics
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from app.rag.page_first_agent import PageFirstAgent
from app.rag.page_first_config import PageFirstConfig

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global agent instance
agent: Optional[PageFirstAgent] = None
agent_config: Optional[PageFirstConfig] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for FastAPI app"""
    global agent, agent_config

    # Startup
    logger.info("Initializing Page-First RAG Agent...")
    try:
        agent_config = PageFirstConfig.from_env()
        agent_config.validate()
        agent = PageFirstAgent(agent_config)
        logger.info("✓ Agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Page-First RAG Agent...")


# FastAPI app
app = FastAPI(
    title="Page-First RAG Agent API",
    description="Question answering API with grounded citations from technical documents",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class Citation(BaseModel):
    """Citation model"""

    doc_id: str = Field(..., description="Document ID")
    page: int = Field(..., description="Page number", ge=1)
    quote: str = Field(..., description="Quoted text", max_length=500)
    evidence_type: Optional[str] = Field(
        None, description="Evidence type: direct_quote|paraphrase"
    )
    confidence: float = Field(..., description="Confidence score [0, 1]", ge=0, le=1)
    fuzzy_score: Optional[float] = Field(None, ge=0, le=1)
    nli_score: Optional[float] = Field(None, ge=0, le=1)
    fixed: Optional[bool] = Field(
        None, description="Whether citation was auto-corrected"
    )


class AskRequest(BaseModel):
    """Request model for /ask endpoint"""

    question: str = Field(
        ..., description="User question", min_length=3, max_length=500
    )
    config_override: Optional[Dict[str, Any]] = Field(
        None, description="Optional config overrides (TOPK_BM25, RERANK_KEEP, etc.)"
    )

    @validator("question")
    def validate_question(cls, v):
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class Metrics(BaseModel):
    """Metrics model"""

    groundedness_est: float = Field(..., description="Estimated groundedness score")
    coverage_est: float = Field(..., description="Citation coverage estimate")
    latency_ms: int = Field(..., description="Total latency in milliseconds")
    steps: Optional[Dict[str, Any]] = Field(
        None, description="Pipeline configuration used"
    )


class RetrievalInfo(BaseModel):
    """Retrieval information"""

    bm25_hits: int
    vector_hits: int
    merged_hits: int
    reranked_hits: int
    llm_usage: Optional[Dict[str, Any]] = None


class AskResponse(BaseModel):
    """Response model for /ask endpoint"""

    answer: str = Field(..., description="Generated answer")
    citations: List[Citation] = Field(..., description="Validated citations")
    language: str = Field(..., description="Detected language (vi|en)")
    metrics: Metrics
    retrieval_info: RetrievalInfo
    error: Optional[str] = Field(None, description="Error message if any")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status: healthy|degraded|unhealthy")
    version: str = Field(..., description="API version")
    agent_ready: bool = Field(..., description="Whether agent is initialized")
    components: Dict[str, str] = Field(..., description="Component status")
    timestamp: float = Field(..., description="Server timestamp")


class MetricsResponse(BaseModel):
    """System metrics response"""

    requests_total: int
    requests_success: int
    requests_error: int
    avg_latency_ms: float
    cache_hit_rate: Optional[float] = None
    uptime_seconds: float


# Global metrics tracking
request_metrics = {
    "total": 0,
    "success": 0,
    "error": 0,
    "latencies": [],
    "start_time": time.time(),
}


# Endpoints
@app.post(
    "/api/v1/ask",
    response_model=AskResponse,
    summary="Ask a question",
    description="Submit a question and get an answer with grounded citations",
)
async def ask_question(request: AskRequest) -> AskResponse:
    """
    Ask a question and receive an answer with citations.

    The agent will:
    1. Retrieve relevant pages from documents
    2. Rerank by relevance
    3. Build context with neighbor pages
    4. Generate answer with LLM
    5. Validate and fix citations

    Returns answer with confidence-scored citations.
    """
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not initialized",
        )

    start_time = time.time()
    request_metrics["total"] += 1

    try:
        logger.info(f"Received question: {request.question[:100]}...")

        # Call agent
        result = agent.answer(request.question)

        # Track metrics
        latency_ms = (time.time() - start_time) * 1000
        request_metrics["success"] += 1
        request_metrics["latencies"].append(latency_ms)

        # Keep only last 100 latencies
        if len(request_metrics["latencies"]) > 100:
            request_metrics["latencies"] = request_metrics["latencies"][-100:]

        logger.info(
            f"Question answered: {len(result['citations'])} citations, "
            f"{latency_ms:.0f}ms"
        )

        # Convert to response model
        return AskResponse(
            answer=result["answer"],
            citations=[Citation(**cite) for cite in result["citations"]],
            language=result["language"],
            metrics=Metrics(**result["metrics"]),
            retrieval_info=RetrievalInfo(**result["retrieval_info"]),
            error=result.get("error"),
        )

    except Exception as e:
        request_metrics["error"] += 1
        logger.error(f"Error processing question: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing question: {str(e)}",
        )


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check service health and component status",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
    - healthy: All components operational
    - degraded: Some components have issues
    - unhealthy: Critical components failed
    """
    components = {}

    # Check agent
    if agent is not None:
        components["agent"] = "healthy"
    else:
        components["agent"] = "unhealthy"

    # Check reranker
    if agent and agent.reranker:
        components["reranker"] = "healthy"
    else:
        components["reranker"] = "degraded"

    # Check NLI validator
    if agent and agent.nli_validator:
        components["nli_validator"] = "healthy"
    else:
        components["nli_validator"] = "degraded"

    # Determine overall status
    if components.get("agent") == "unhealthy":
        overall_status = "unhealthy"
    elif any(v == "degraded" for v in components.values()):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return HealthResponse(
        status=overall_status,
        version="2.0.0",
        agent_ready=agent is not None,
        components=components,
        timestamp=time.time(),
    )


@app.get(
    "/api/v1/metrics",
    response_model=MetricsResponse,
    summary="System metrics",
    description="Get system performance metrics",
)
async def get_metrics() -> MetricsResponse:
    """
    System metrics endpoint.

    Returns request counts, latencies, and uptime.
    """
    latencies = request_metrics["latencies"]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    uptime = time.time() - request_metrics["start_time"]

    # Cache hit rate (if available)
    cache_hit_rate = None
    if agent and agent.reranker and hasattr(agent.reranker, "get_cache_stats"):
        try:
            cache_stats = agent.reranker.get_cache_stats()
            rank_cache = cache_stats.get("rank_cache", {})
            if rank_cache.get("enabled"):
                cache_hit_rate = rank_cache.get("hit_rate", 0.0)
        except:
            pass

    return MetricsResponse(
        requests_total=request_metrics["total"],
        requests_success=request_metrics["success"],
        requests_error=request_metrics["error"],
        avg_latency_ms=avg_latency,
        cache_hit_rate=cache_hit_rate,
        uptime_seconds=uptime,
    )


@app.get("/", summary="Root", include_in_schema=False)
async def root():
    """Root endpoint redirect"""
    return {
        "message": "Page-First RAG Agent API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.page_first_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
