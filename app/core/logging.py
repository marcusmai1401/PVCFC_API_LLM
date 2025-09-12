"""
Cấu hình logging cho ứng dụng sử dụng loguru
Bao gồm middleware để log requests và mask sensitive data
"""
import json
import time
import uuid
from typing import Any, Dict

from fastapi import Request
from fastapi.responses import Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware để log tất cả requests và responses"""

    async def dispatch(self, request: Request, call_next):
        # Tạo trace_id duy nhất cho request
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id

        # Ghi log request
        start_time = time.time()

        # Mask sensitive headers
        headers = dict(request.headers)
        headers = self._mask_sensitive_data(headers)

        # Log request info
        request_info = {
            "trace_id": trace_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else "unknown",
            "headers": headers,
        }

        logger.info(f"Request started", extra=request_info)

        # Gọi handler tiếp theo
        try:
            response: Response = await call_next(request)

            # Tính latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Log response
            response_info = {
                "trace_id": trace_id,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            }

            logger.info(f"Request completed", extra=response_info)

            # Thêm trace_id vào response headers
            response.headers["X-Trace-ID"] = trace_id

            return response

        except Exception as e:
            # Log lỗi
            latency_ms = int((time.time() - start_time) * 1000)
            error_info = {
                "trace_id": trace_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "latency_ms": latency_ms,
            }
            logger.error(f"Request failed", extra=error_info)
            raise

    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive information trong logs"""
        masked = {}
        sensitive_keys = {
            "authorization",
            "x-api-key",
            "cookie",
            "openai_api_key",
            "gemini_api_key",
            "api-key",
        }

        for key, value in data.items():
            if key.lower() in sensitive_keys:
                masked[key] = "***MASKED***"
            else:
                masked[key] = value

        return masked


def setup_logging():
    """Thiết lập cấu hình logging"""

    # Remove default handler
    logger.remove()

    # Console handler với format đẹp cho dev
    if settings.app_env in ["local", "dev"]:
        logger.add(
            sink=lambda msg: print(msg, end=""),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> - "
            "<level>{message}</level>",
            level=settings.log_level,
            colorize=True,
        )

    # File handler với format JSON cho production
    if settings.app_env == "prod":
        logger.add(
            sink="logs/app.log",
            format="{time} | {level} | {name}:{function}:{line} | {message}",
            level=settings.log_level,
            rotation="10 MB",
            retention="30 days",
            serialize=True,  # JSON format
        )

    # Request logs luôn ghi ra file JSONL
    logger.add(
        sink="logs/requests.jsonl",
        format="{message}",
        level="INFO",
        filter=lambda record: "trace_id" in record["extra"],
        serialize=True,
    )

    logger.info(
        f"Logging initialized - Level: {settings.log_level}, Env: {settings.app_env}"
    )


# Convenience function để lấy logger với trace_id
def get_logger_with_trace(request: Request = None):
    """Lấy logger với trace_id từ request"""
    if request and hasattr(request.state, "trace_id"):
        return logger.bind(trace_id=request.state.trace_id)
    return logger
