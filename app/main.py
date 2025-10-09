"""
PVCFC RAG API - Main FastAPI Application
Retrieval-Augmented Generation API cho tài liệu kỹ thuật PVCFC
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger

from app.api.endpoints import pdf_renderer
from app.api.routers import ask, health, locate, report
from app.core.config import settings
from app.core.logging import LoggingMiddleware, setup_logging
from app.core.metrics import get_metrics, get_metrics_content_type
from app.core.rate_limit import RateLimitMiddleware, configure_rate_limiter
from app.core.tracing import TracingMiddleware, get_current_trace
from app.deps.indices import get_index_manager, startup_indices


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info(f"PVCFC RAG API starting...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(
        f"LLM Provider: {settings.llm_provider} (Ready: {settings.llm_provider_ready})"
    )
    logger.info(f"Port: {settings.api_port}")
    logger.info(f"Version: {settings.version} ({settings.commit_sha[:8]})")

    # Initialize indices and dependencies
    try:
        # Load search indices
        result = await startup_indices(settings)
        if result["status"] == "loaded":
            logger.info(
                f"Indices loaded: BM25={result['bm25_ready']}, FAISS={result['faiss_ready']}"
            )
            # Store retriever in app state
            manager = get_index_manager(settings)
            app.state.retriever = manager.get_retriever()
            app.state.settings = settings

            # Load doc_id_map if available (prioritize production path)
            import json
            from pathlib import Path

            production_path = Path("artifacts/ingestion_production/doc_id_map.json")
            legacy_path = Path("artifacts/ingestion/doc_id_map.json")

            loaded = False
            if production_path.exists():
                try:
                    with open(production_path, "r", encoding="utf-8") as f:
                        app.state.doc_id_map = json.load(f)
                    logger.info(
                        f"Loaded doc_id_map from production with {len(app.state.doc_id_map)} entries"
                    )
                    loaded = True
                except Exception as e:
                    logger.warning(f"Failed to load doc_id_map from production: {e}")

            if not loaded and legacy_path.exists():
                try:
                    with open(legacy_path, "r", encoding="utf-8") as f:
                        app.state.doc_id_map = json.load(f)
                    logger.info(
                        f"Loaded doc_id_map from legacy path with {len(app.state.doc_id_map)} entries"
                    )
                    loaded = True
                except Exception as e:
                    logger.warning(f"Failed to load doc_id_map from legacy path: {e}")

            if not loaded:
                logger.info("No doc_id_map.json found, citations will use doc_id only")
                app.state.doc_id_map = {}
        else:
            logger.warning(f"Indices not fully loaded: {result}")
    except Exception as e:
        logger.error(f"Failed to initialize indices: {str(e)}")
        # App can still run without indices for health checks

    # Configure rate limiter
    configure_rate_limiter(requests_per_minute=60, burst_size=20, per_ip=True)

    logger.info("Startup completed")

    yield

    # Shutdown
    logger.info("PVCFC RAG API shutting down...")
    logger.info("Shutdown completed")


def create_app() -> FastAPI:
    """Factory function để tạo FastAPI application"""

    # Khởi tạo logging trước khi tạo app
    setup_logging()

    # Tạo FastAPI instance với lifespan
    app = FastAPI(
        title="PVCFC RAG API",
        description=(
            "Hệ thống API Truy vấn Tài liệu Kỹ thuật PVCFC\n"
            "Sử dụng RAG (Retrieval-Augmented Generation) để truy xuất và phân tích "
            "tri thức từ tài liệu kỹ thuật đa định dạng."
        ),
        version=settings.version,
        docs_url="/docs" if settings.app_env != "prod" else None,
        redoc_url="/redoc" if settings.app_env != "prod" else None,
        lifespan=lifespan,
    )

    # Middleware cho CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"]
        if settings.app_env == "local"
        else ["https://your-domain.com"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Logging middleware - phải thêm trước các middleware khác
    app.add_middleware(LoggingMiddleware)

    # Add tracing middleware
    app.add_middleware(TracingMiddleware)

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # Include routers
    app.include_router(health.router, tags=["Health"])

    # Phase 2 routers - RAG endpoints
    app.include_router(ask.router, tags=["Query"])
    app.include_router(locate.router, tags=["Location"])
    app.include_router(report.router, tags=["Reports"])

    # PDF rendering endpoints
    app.include_router(pdf_renderer.router, tags=["PDF"])

    # Metrics endpoint (Prometheus format)
    @app.get("/metrics", tags=["Monitoring"], response_class=PlainTextResponse)
    async def metrics_endpoint():
        """Get Prometheus metrics"""
        return PlainTextResponse(
            content=get_metrics(), media_type=get_metrics_content_type()
        )

    # Trace endpoint
    @app.get("/trace", tags=["Monitoring"])
    async def trace_endpoint():
        """Get current trace"""
        trace = get_current_trace()
        if trace:
            return trace
        return {"message": "No active trace"}

    # Index stats endpoint
    @app.get("/index-stats", tags=["Monitoring"])
    async def index_stats():
        """Get index statistics"""
        manager = get_index_manager()
        return manager.get_index_stats()

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handler cho tất cả unhandled exceptions"""
        trace_id = getattr(request.state, "trace_id", "unknown")

        logger.error(
            f"Unhandled exception: {exc}",
            extra={
                "trace_id": trace_id,
                "url": str(request.url),
                "method": request.method,
                "exception_type": type(exc).__name__,
            },
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "trace_id": trace_id,
                "message": "An unexpected error occurred. Please check logs for details.",
            },
            headers={"X-Trace-ID": trace_id},
        )

    return app


# Tạo app instance
app = create_app()


if __name__ == "__main__":
    # Run app directly (cho development)
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",  # bind to localhost for development
        port=settings.api_port,
        reload=settings.app_env == "local",
        log_config=None,  # Sử dụng loguru thay vì uvicorn logging
    )
