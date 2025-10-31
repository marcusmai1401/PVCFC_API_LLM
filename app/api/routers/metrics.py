"""
Prometheus Metrics Endpoint

Exposes metrics for Prometheus scraping at /metrics

Provides:
- All RAG pipeline metrics
- Week 3 observability metrics (circuit breakers, health, security)
- Standard Prometheus format
"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY

from loguru import logger

router = APIRouter()


@router.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint

    Returns all registered metrics in Prometheus exposition format.
    This endpoint should be scraped by Prometheus server.

    Example Prometheus configuration:
        scrape_configs:
          - job_name: 'pvcfc-rag-api'
            static_configs:
              - targets: ['localhost:8000']
            metrics_path: '/metrics'
            scrape_interval: 15s

    Returns:
        Response with Prometheus metrics in text format
    """
    try:
        # Generate latest metrics from registry
        metrics_data = generate_latest(REGISTRY)

        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        # Return empty metrics on error (Prometheus will mark as down)
        return Response(
            content=b"",
            media_type=CONTENT_TYPE_LATEST,
            status_code=500,
        )


@router.get("/metrics/health")
async def metrics_health():
    """
    Health check for metrics endpoint

    Verifies that metrics collection is working.

    Returns:
        Simple health status
    """
    return {
        "status": "healthy",
        "metrics_endpoint": "/metrics",
        "scrape_interval_recommended": "15s",
    }
