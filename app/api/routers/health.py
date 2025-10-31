"""
Health check endpoint cho monitoring và load balancer
Trả về thông tin version, uptime và trạng thái các service
"""
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Request
from loguru import logger

from app.core.config import settings
from app.core.health_checker import HealthChecker

router = APIRouter()

# Lưu thời điểm start app
_start_time = time.time()


@router.get("/healthz")
async def health_check(request: Request) -> Dict[str, Any]:
    """
    Legacy health check endpoint - simple liveness probe.

    Returns basic app info and uptime. For detailed readiness checks,
    use the /readyz endpoint.
    """
    # Tính uptime
    current_time = time.time()
    uptime_seconds = int(current_time - _start_time)
    uptime_human = _format_uptime(uptime_seconds)

    # Tạo response
    health_data = {
        "status": "healthy",
        "app_env": settings.app_env,
        "version": settings.version,
        "commit_sha": settings.commit_sha,
        "uptime_seconds": uptime_seconds,
        "uptime_human": uptime_human,
        "llm_provider": settings.llm_provider,
        "llm_provider_ready": settings.llm_provider_ready,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # Log health check (với trace_id nếu có)
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.debug(f"Health check requested", extra={"trace_id": trace_id})

    return health_data


@router.get("/livez")
async def liveness_check(request: Request) -> Dict[str, Any]:
    """
    Kubernetes liveness probe - is the app alive?

    Quick check to see if the process is responsive.
    Should always return 200 unless the process is dead.
    """
    health_checker = HealthChecker(request.app.state)
    return await health_checker.check_all(check_type="liveness")


@router.get("/readyz")
async def readiness_check(request: Request) -> Dict[str, Any]:
    """
    Kubernetes readiness probe - can the app serve traffic?

    Deep checks of all dependencies:
    - Weaviate (vector database)
    - OpenSearch (BM25 search)
    - Redis (cache/conversation state)
    - File system (index directories)

    Returns:
        - status: "healthy", "degraded", or "unhealthy"
        - components: individual component health statuses
        - check_duration_ms: time taken to perform all checks
    """
    health_checker = HealthChecker(request.app.state)
    result = await health_checker.check_all(check_type="readiness")

    # Log degraded or unhealthy states
    trace_id = getattr(request.state, "trace_id", "unknown")
    if result["status"] != "healthy":
        logger.warning(
            f"Readiness check: {result['status']}",
            extra={"trace_id": trace_id, "components": result.get("components", [])},
        )

    return result


def _format_uptime(seconds: int) -> str:
    """Format uptime thành dạng human-readable"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)
