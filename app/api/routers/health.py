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

router = APIRouter()

# Lưu thời điểm start app
_start_time = time.time()


@router.get("/healthz")
async def health_check(request: Request) -> Dict[str, Any]:
    """
    Endpoint kiểm tra sức khỏe ứng dụng

    Returns:
        - status: "healthy"
        - app_env: môi trường hiện tại
        - version: phiên bản ứng dụng
        - commit_sha: git commit hash
        - uptime_seconds: thời gian chạy tính bằng giây
        - uptime_human: thời gian chạy dạng human-readable
        - llm_provider_ready: có sẵn sàng kết nối LLM không
        - timestamp: thời gian hiện tại ISO
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
