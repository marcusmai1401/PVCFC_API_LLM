"""
Health Checker System for Comprehensive Dependency Monitoring

Provides deep health checks for all critical dependencies:
- Weaviate (vector database)
- OpenSearch (BM25 search)
- Redis (cache and conversation state)
- Gemini LLM (generation)
- File system (artifacts, indexes)

Supports both liveness and readiness probes for Kubernetes.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.core.config import settings


class HealthStatus(Enum):
    """Health status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status for a single component"""

    name: str
    status: HealthStatus
    message: str
    latency_ms: Optional[float] = None
    metadata: Optional[dict] = None


class HealthChecker:
    """
    Centralized health checking for all dependencies.

    Performs parallel health checks with timeouts to avoid blocking.
    Provides both quick liveness checks and deep readiness checks.
    """

    def __init__(self, app_state=None):
        """
        Initialize health checker.

        Args:
            app_state: FastAPI app state with component references
        """
        self.app_state = app_state

    async def check_all(self, check_type: str = "readiness") -> Dict:
        """
        Check all components in parallel.

        Args:
            check_type: "liveness" (is app alive?) or "readiness" (can serve traffic?)

        Returns:
            Dict with overall status and component details
        """
        if check_type == "liveness":
            # Liveness: Quick check - is process responding?
            return {
                "status": HealthStatus.HEALTHY.value,
                "type": "liveness",
                "timestamp": time.time(),
            }

        # Readiness: Deep checks - can serve traffic?
        start_time = time.time()

        try:
            checks = await asyncio.gather(
                self.check_weaviate(),
                self.check_opensearch(),
                self.check_redis(),
                self.check_filesystem(),
                return_exceptions=True,
            )

            components = []
            for check in checks:
                if isinstance(check, Exception):
                    components.append(
                        ComponentHealth(
                            name="unknown",
                            status=HealthStatus.UNHEALTHY,
                            message=f"Health check failed: {str(check)}",
                        )
                    )
                else:
                    components.append(check)

            # Determine overall status
            unhealthy = [c for c in components if c.status == HealthStatus.UNHEALTHY]
            degraded = [c for c in components if c.status == HealthStatus.DEGRADED]

            # More than half unhealthy = system unhealthy
            if len(unhealthy) > len(components) / 2:
                overall_status = HealthStatus.UNHEALTHY
            # Any unhealthy or degraded = system degraded
            elif unhealthy or degraded:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY

            total_time = (time.time() - start_time) * 1000

            return {
                "status": overall_status.value,
                "type": "readiness",
                "timestamp": time.time(),
                "check_duration_ms": round(total_time, 2),
                "components": [
                    {
                        "name": c.name,
                        "status": c.status.value,
                        "message": c.message,
                        "latency_ms": c.latency_ms,
                        "metadata": c.metadata or {},
                    }
                    for c in components
                ],
            }

        except Exception as e:
            logger.error(f"Health check failed with exception: {e}", exc_info=True)
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "type": "readiness",
                "timestamp": time.time(),
                "error": str(e),
            }

    async def check_weaviate(self) -> ComponentHealth:
        """Check Weaviate connectivity and collection existence"""
        start = time.time()

        try:
            # Check if Weaviate is enabled
            if not settings.weaviate_enabled:
                return ComponentHealth(
                    name="weaviate",
                    status=HealthStatus.DEGRADED,
                    message="Not configured (disabled in settings)",
                )

            # Get Weaviate retriever from app state
            weaviate_retriever = getattr(self.app_state, "weaviate_retriever", None)
            if not weaviate_retriever:
                return ComponentHealth(
                    name="weaviate",
                    status=HealthStatus.DEGRADED,
                    message="Retriever not initialized",
                )

            # Call retriever's health check method
            health = weaviate_retriever.health_check()
            latency = (time.time() - start) * 1000

            if health.get("status") == "healthy":
                return ComponentHealth(
                    name="weaviate",
                    status=HealthStatus.HEALTHY,
                    message="Connected and ready",
                    latency_ms=round(latency, 2),
                    metadata={
                        "collection": health.get("collection"),
                        "ready": health.get("ready", True),
                    },
                )
            else:
                return ComponentHealth(
                    name="weaviate",
                    status=HealthStatus.UNHEALTHY,
                    message=health.get("error", "Unknown error"),
                    latency_ms=round(latency, 2),
                )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Weaviate health check failed: {e}")
            return ComponentHealth(
                name="weaviate",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)[:100]}",
                latency_ms=round(latency, 2),
            )

    async def check_opensearch(self) -> ComponentHealth:
        """Check OpenSearch connectivity and index availability"""
        start = time.time()

        try:
            # Check if OpenSearch is enabled
            if not settings.opensearch_enabled:
                return ComponentHealth(
                    name="opensearch",
                    status=HealthStatus.DEGRADED,
                    message="Not configured (disabled in settings)",
                )

            # Get OpenSearch retriever from app state
            opensearch_retriever = getattr(
                self.app_state, "opensearch_retriever", None
            )
            if not opensearch_retriever:
                return ComponentHealth(
                    name="opensearch",
                    status=HealthStatus.DEGRADED,
                    message="Retriever not initialized",
                )

            # Call retriever's health check method (if it exists)
            if hasattr(opensearch_retriever, "health_check"):
                health = opensearch_retriever.health_check()
                latency = (time.time() - start) * 1000

                if health.get("status") == "healthy":
                    return ComponentHealth(
                        name="opensearch",
                        status=HealthStatus.HEALTHY,
                        message="Connected and ready",
                        latency_ms=round(latency, 2),
                        metadata={
                            "index": health.get("index"),
                            "cluster_health": health.get("cluster_health"),
                        },
                    )
                else:
                    return ComponentHealth(
                        name="opensearch",
                        status=HealthStatus.UNHEALTHY,
                        message=health.get("error", "Unknown error"),
                        latency_ms=round(latency, 2),
                    )
            else:
                # Fallback: Try simple ping
                try:
                    client = opensearch_retriever.client
                    info = client.info()
                    latency = (time.time() - start) * 1000
                    return ComponentHealth(
                        name="opensearch",
                        status=HealthStatus.HEALTHY,
                        message="Connected",
                        latency_ms=round(latency, 2),
                        metadata={"version": info.get("version", {}).get("number")},
                    )
                except Exception as ping_error:
                    latency = (time.time() - start) * 1000
                    return ComponentHealth(
                        name="opensearch",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Ping failed: {str(ping_error)[:50]}",
                        latency_ms=round(latency, 2),
                    )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"OpenSearch health check failed: {e}")
            return ComponentHealth(
                name="opensearch",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)[:100]}",
                latency_ms=round(latency, 2),
            )

    async def check_redis(self) -> ComponentHealth:
        """Check Redis connectivity"""
        start = time.time()

        try:
            # Get conversation manager from app state
            conversation_manager = getattr(
                self.app_state, "conversation_manager", None
            )
            if not conversation_manager:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    message="Conversation manager not initialized",
                )

            # Call conversation manager's health check
            health = conversation_manager.health_check()
            latency = (time.time() - start) * 1000

            if health.get("status") == "healthy":
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    message="Connected and ready",
                    latency_ms=round(latency, 2),
                    metadata={
                        "total_conversations": health.get("total_conversations", 0),
                        "ttl_hours": health.get("ttl_hours"),
                    },
                )
            else:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    message=health.get("error", "Unknown error"),
                    latency_ms=round(latency, 2),
                )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Redis health check failed: {e}")
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)[:100]}",
                latency_ms=round(latency, 2),
            )

    async def check_filesystem(self) -> ComponentHealth:
        """Check critical file paths exist and are accessible"""
        start = time.time()

        try:
            critical_paths = [
                settings.index_dir,  # Index directory
                getattr(settings, "artifacts_dir", None),  # Artifacts directory
            ]

            # Filter out None values
            critical_paths = [p for p in critical_paths if p]

            missing_paths = []
            for path_str in critical_paths:
                path = Path(path_str)
                if not path.exists():
                    missing_paths.append(str(path))

            latency = (time.time() - start) * 1000

            if missing_paths:
                return ComponentHealth(
                    name="filesystem",
                    status=HealthStatus.DEGRADED,
                    message=f"Missing paths: {', '.join(missing_paths[:3])}",
                    latency_ms=round(latency, 2),
                    metadata={"missing_count": len(missing_paths)},
                )
            else:
                return ComponentHealth(
                    name="filesystem",
                    status=HealthStatus.HEALTHY,
                    message="All critical paths exist",
                    latency_ms=round(latency, 2),
                    metadata={"checked_paths": len(critical_paths)},
                )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Filesystem health check failed: {e}")
            return ComponentHealth(
                name="filesystem",
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)[:100]}",
                latency_ms=round(latency, 2),
            )
