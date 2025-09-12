"""
PVCFC RAG API - Main FastAPI Application
Retrieval-Augmented Generation API cho tài liệu kỹ thuật PVCFC
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.routers import health
from app.core.config import settings
from app.core.logging import LoggingMiddleware, setup_logging


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

    # TODO Phase 1+: Khởi tạo index, load models, warm up cache
    logger.info("Startup completed")

    yield

    # Shutdown
    logger.info("PVCFC RAG API shutting down...")
    # TODO Phase 1+: Cleanup resources, close connections
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

    # Include routers
    app.include_router(health.router, tags=["Health"])

    # Placeholder routers cho các phase sau
    # app.include_router(ask.router, prefix="/api/v1", tags=["Query"])
    # app.include_router(locate.router, prefix="/api/v1", tags=["Location"])
    # app.include_router(report.router, prefix="/api/v1", tags=["Reports"])

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
        host="0.0.0.0",
        port=settings.api_port,
        reload=settings.app_env == "local",
        log_config=None,  # Sử dụng loguru thay vì uvicorn logging
    )
