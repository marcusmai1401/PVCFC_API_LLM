"""
Rate limiting for RAG API endpoints.
"""
import logging
import time
from collections import defaultdict
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket algorithm for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens (burst size)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> Tuple[bool, int]:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            Tuple of (success, remaining_tokens)
        """
        # Refill bucket
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate

        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

        # Try to consume
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, int(self.tokens)

        return False, int(self.tokens)

    def time_until_tokens(self, tokens: int = 1) -> float:
        """
        Calculate time until tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Seconds until tokens available
        """
        if self.tokens >= tokens:
            return 0

        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """Rate limiter for API endpoints."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 20,
        per_ip: bool = True,
        per_tenant: bool = False,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Sustained request rate
            burst_size: Maximum burst size
            per_ip: Apply limits per IP address
            per_tenant: Apply limits per tenant ID
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.per_ip = per_ip
        self.per_tenant = per_tenant

        # Token buckets for each client
        self.buckets: Dict[str, TokenBucket] = {}

        # Calculate refill rate (tokens per second)
        self.refill_rate = requests_per_minute / 60.0

    def _get_client_id(self, request: Request) -> str:
        """
        Get client identifier from request.

        Args:
            request: FastAPI request

        Returns:
            Client identifier
        """
        identifiers = []

        if self.per_ip:
            # Get client IP
            client_ip = request.client.host if request.client else "unknown"
            # Check for X-Forwarded-For header (proxy/load balancer)
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
            identifiers.append(f"ip:{client_ip}")

        if self.per_tenant:
            # Get tenant ID from header or auth
            tenant_id = request.headers.get("X-Tenant-ID", "default")
            identifiers.append(f"tenant:{tenant_id}")

        if not identifiers:
            identifiers.append("global")

        return ":".join(identifiers)

    def _get_or_create_bucket(self, client_id: str) -> TokenBucket:
        """
        Get or create token bucket for client.

        Args:
            client_id: Client identifier

        Returns:
            TokenBucket instance
        """
        if client_id not in self.buckets:
            self.buckets[client_id] = TokenBucket(
                capacity=self.burst_size, refill_rate=self.refill_rate
            )
        return self.buckets[client_id]

    async def check_rate_limit(self, request: Request) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limits.

        Args:
            request: FastAPI request

        Returns:
            Tuple of (allowed, metadata)
        """
        client_id = self._get_client_id(request)
        bucket = self._get_or_create_bucket(client_id)

        # Try to consume a token
        allowed, remaining = bucket.consume(1)

        metadata = {
            "client_id": client_id,
            "remaining": remaining,
            "limit": self.requests_per_minute,
            "burst": self.burst_size,
        }

        if not allowed:
            # Calculate retry time
            retry_after = bucket.time_until_tokens(1)
            metadata["retry_after"] = int(retry_after) + 1

            logger.warning(f"Rate limit exceeded for {client_id}")

        return allowed, metadata


class RateLimitMiddleware:
    """Middleware for rate limiting."""

    def __init__(
        self,
        app,
        rate_limiter: Optional[RateLimiter] = None,
        exclude_paths: Optional[list] = None,
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            rate_limiter: RateLimiter instance
            exclude_paths: Paths to exclude from rate limiting
        """
        self.app = app
        self.rate_limiter = rate_limiter or RateLimiter()
        self.exclude_paths = exclude_paths or [
            "/healthz",
            "/metrics",
            "/docs",
            "/openapi.json",
        ]

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope["path"]

            # Skip excluded paths
            if path in self.exclude_paths:
                await self.app(scope, receive, send)
                return

            # Create request object
            request = Request(scope, receive)

            # Check rate limit
            allowed, metadata = await self.rate_limiter.check_rate_limit(request)

            if not allowed:
                # Rate limit exceeded
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Please retry after {metadata['retry_after']} seconds.",
                        "retry_after": metadata["retry_after"],
                    },
                    headers={
                        "X-RateLimit-Limit": str(metadata["limit"]),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(
                            int(time.time()) + metadata["retry_after"]
                        ),
                        "Retry-After": str(metadata["retry_after"]),
                    },
                )
                await response(scope, receive, send)
                return

            # Add rate limit headers to response
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.extend(
                        [
                            (b"x-ratelimit-limit", str(metadata["limit"]).encode()),
                            (
                                b"x-ratelimit-remaining",
                                str(metadata["remaining"]).encode(),
                            ),
                            (b"x-ratelimit-reset", str(int(time.time()) + 60).encode()),
                        ]
                    )
                    message["headers"] = headers

                await send(message)

            # Continue with request
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


# Global rate limiter
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def configure_rate_limiter(
    requests_per_minute: int = 60,
    burst_size: int = 20,
    per_ip: bool = True,
    per_tenant: bool = False,
):
    """Configure the global rate limiter."""
    global _rate_limiter
    _rate_limiter = RateLimiter(
        requests_per_minute=requests_per_minute,
        burst_size=burst_size,
        per_ip=per_ip,
        per_tenant=per_tenant,
    )
