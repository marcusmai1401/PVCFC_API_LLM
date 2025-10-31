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
from app.api.routers import ask, config, health, locate, report, tags
from app.core.config import settings
from app.core.logging import LoggingMiddleware, setup_logging
from app.core.metrics import get_metrics, get_metrics_content_type
from app.core.rate_limit import RateLimitMiddleware, configure_rate_limiter
from app.core.redis_client import get_redis_factory
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

    # Initialize Redis client factory
    try:
        redis_factory = get_redis_factory()
        redis_factory.initialize()
        logger.info(f"Redis client initialized in {redis_factory.mode} mode")
        app.state.redis_factory = redis_factory
    except Exception as e:
        logger.error(
            f"Failed to initialize Redis client: {e}. "
            "Redis-dependent features (conversation history, distributed cache) will be unavailable.",
            exc_info=True,
        )
        app.state.redis_factory = None

    # Initialize indices and dependencies
    try:
        # Load search indices
        result = await startup_indices(settings)
        if result["status"] == "loaded":
            # Log based on retriever type
            retriever_type = result.get("retriever_type", "unknown")
            if retriever_type == "weaviate":
                logger.info(
                    f"Indices loaded: Weaviate (ready={result.get('retriever_ready', False)})"
                )
            else:
                logger.info(
                    f"Indices loaded: BM25={result.get('bm25_ready', False)}, FAISS={result.get('faiss_ready', False)}"
                )
            # Store retriever in app state
            manager = get_index_manager(settings)
            app.state.retriever = manager.get_retriever()
            app.state.settings = settings

            # Initialize specialized retrievers
            try:
                # P&ID Tags Retriever (if enabled)
                from app.rag.hybrid_with_tags_retriever import HybridWithTagsRetriever

                app.state.tags_retriever = HybridWithTagsRetriever()
                logger.info("Initialized P&ID tags retriever")
            except Exception as e:
                logger.warning(f"Failed to init tags retriever: {e}")
                app.state.tags_retriever = None

            try:
                # Technical Document Retriever (NEW)
                from app.rag.technical_doc_retriever import TechnicalDocRetriever

                app.state.tech_doc_retriever = TechnicalDocRetriever()
                logger.info("Initialized Technical Document retriever")
            except Exception as e:
                logger.warning(f"Failed to init technical doc retriever: {e}")
                app.state.tech_doc_retriever = None

            # Attach OpenSearch client to app state for routers needing direct access (e.g., /tags)
            try:
                retriever = app.state.retriever
                # Modern hybrid retriever exposes opensearch_retriever
                if (
                    hasattr(retriever, "opensearch_retriever")
                    and retriever.opensearch_retriever
                ):
                    app.state.opensearch_client = retriever.opensearch_retriever.client
                    logger.info(
                        "Attached OpenSearch client from Hybrid Modern retriever"
                    )
                # Legacy hybrid may expose bm25_indexer as OpenSearch retriever when enabled
                elif hasattr(retriever, "bm25_indexer") and retriever.bm25_indexer:
                    from app.rag.indexers.opensearch_bm25_retriever import (
                        OpenSearchBM25Retriever,
                    )

                    if isinstance(retriever.bm25_indexer, OpenSearchBM25Retriever):
                        app.state.opensearch_client = retriever.bm25_indexer.client
                        logger.info(
                            "Attached OpenSearch client from Legacy Hybrid retriever"
                        )
            except Exception as e:
                logger.warning(f"Could not attach OpenSearch client to app state: {e}")

            # Load doc_id_map if available (prioritize production path)
            import json
            from pathlib import Path

            production_path = Path("artifacts/ingestion_production/doc_id_map.json")
            legacy_path = Path("artifacts/ingestion/doc_id_map.json")

            loaded = False
            production_map = None
            legacy_map = None

            # BUG-027 FIX: Load both maps and validate consistency
            if production_path.exists():
                try:
                    with open(production_path, "r", encoding="utf-8") as f:
                        production_map = json.load(f)
                    logger.info(
                        f"Loaded production doc_id_map with {len(production_map)} entries"
                    )
                except Exception as e:
                    logger.warning(f"Failed to load doc_id_map from production: {e}")

            if legacy_path.exists():
                try:
                    with open(legacy_path, "r", encoding="utf-8") as f:
                        legacy_map = json.load(f)
                    logger.info(
                        f"Loaded legacy doc_id_map with {len(legacy_map)} entries"
                    )
                except Exception as e:
                    logger.warning(f"Failed to load doc_id_map from legacy path: {e}")

            # BUG-027 FIX: Validate consistency if both exist
            if production_map and legacy_map:
                logger.info(
                    "Both production and legacy doc_id_maps exist, validating consistency..."
                )

                # Check if maps have different sizes
                if len(production_map) != len(legacy_map):
                    logger.warning(
                        f"⚠️ Doc ID map size mismatch: "
                        f"production={len(production_map)}, legacy={len(legacy_map)}. "
                        f"This may indicate incomplete re-ingestion or version mismatch."
                    )

                # Sample check: verify common doc_ids point to same PDFs
                common_ids = set(production_map.keys()) & set(legacy_map.keys())
                if common_ids:
                    sample_ids = list(common_ids)[:5]  # Check first 5 common IDs
                    mismatches = []
                    for doc_id in sample_ids:
                        prod_val = production_map[doc_id]
                        legacy_val = legacy_map[doc_id]
                        # Extract pdf_path from dict or use string directly
                        prod_path = (
                            prod_val.get("pdf_path")
                            if isinstance(prod_val, dict)
                            else prod_val
                        )
                        legacy_path_str = (
                            legacy_val.get("pdf_path")
                            if isinstance(legacy_val, dict)
                            else legacy_val
                        )

                        if prod_path != legacy_path_str:
                            mismatches.append((doc_id, prod_path, legacy_path_str))

                    if mismatches:
                        logger.error(
                            f"⚠️ CRITICAL: Doc ID mapping inconsistency detected! "
                            f"{len(mismatches)} mismatches in sample. Examples:"
                        )
                        for doc_id, prod, leg in mismatches[:2]:
                            logger.error(
                                f"  - {doc_id}: production={prod}, legacy={leg}"
                            )
                        logger.error(
                            "This will cause citations to point to wrong PDFs! "
                            "Consider re-ingesting to sync maps."
                        )
                    else:
                        logger.info(
                            "✓ Doc ID maps appear consistent (sample check passed)"
                        )

            # Use production if available, otherwise legacy
            if production_map:
                app.state.doc_id_map = production_map
                loaded = True
                logger.info(
                    f"Using production doc_id_map ({len(production_map)} entries)"
                )
            elif legacy_map:
                app.state.doc_id_map = legacy_map
                loaded = True
                logger.info(f"Using legacy doc_id_map ({len(legacy_map)} entries)")

            if not loaded:
                logger.info("No doc_id_map.json found, citations will use doc_id only")
                app.state.doc_id_map = {}
        else:
            logger.warning(f"Indices not fully loaded: {result}")
    except Exception as e:
        logger.error(f"Failed to initialize indices: {str(e)}")
        # App can still run without indices for health checks

    # Initialize conversation manager (multi-turn chat)
    try:
        from app.core.conversation.manager import ConversationManager

        conversation_manager = ConversationManager(
            redis_url=settings.redis_url,
            redis_password=settings.redis_password,
            ttl_hours=settings.conversation_ttl_hours,
            max_turns_per_conversation=settings.max_turns_per_conversation,
            max_context_tokens=settings.max_conversation_context_tokens,
        )
        app.state.conversation_manager = conversation_manager
        health = conversation_manager.health_check()
        logger.info(f"Conversation manager initialized: {health}")
    except Exception as e:
        logger.warning(
            f"Failed to initialize conversation manager (Redis unavailable): {e}. "
            "Multi-turn chat will be disabled."
        )
        app.state.conversation_manager = None

    # Configure rate limiter
    configure_rate_limiter(requests_per_minute=60, burst_size=20, per_ip=True)

    logger.info("Startup completed")

    yield

    # Shutdown
    logger.info("PVCFC RAG API shutting down...")

    # Close Redis connections
    if hasattr(app.state, "redis_factory") and app.state.redis_factory:
        try:
            await app.state.redis_factory.close()
            logger.info("Redis client shutdown complete")
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}", exc_info=True)

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

    # Metadata router - Tags listing
    app.include_router(tags.router, tags=["Metadata"])

    # Phase 4 router - Configuration management
    app.include_router(config.router, tags=["Configuration"])

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
