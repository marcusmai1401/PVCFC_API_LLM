"""
Week 3: Enhanced Metrics for Observability

Adds metrics for:
- Circuit breakers (state, failures, recoveries)
- Health checks (component status, check duration)
- Document security (validations, denials, audits)
- HTTP requests (detailed tracking)

Extends existing metrics.py with Week 2 integration.
"""

from functools import wraps
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram

from loguru import logger

# ========================================
# Week 3: Circuit Breaker Metrics
# ========================================

# Circuit breaker state (0=closed, 1=open, 2=half_open)
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service"],
)

# Circuit breaker failures
circuit_breaker_failures_total = Counter(
    "circuit_breaker_failures_total",
    "Circuit breaker failure count",
    ["service"],
)

# Circuit breaker successes
circuit_breaker_successes_total = Counter(
    "circuit_breaker_successes_total",
    "Circuit breaker success count",
    ["service"],
)

# Circuit breaker state changes
circuit_breaker_state_changes_total = Counter(
    "circuit_breaker_state_changes_total",
    "Circuit breaker state changes",
    ["service", "from_state", "to_state"],
)

# Circuit breaker open duration
circuit_breaker_open_duration_seconds = Histogram(
    "circuit_breaker_open_duration_seconds",
    "Time circuit breaker stays open",
    ["service"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
)

# ========================================
# Week 3: Health Check Metrics
# ========================================

# Component health status (1=healthy, 0.5=degraded, 0=unhealthy)
component_health_status = Gauge(
    "component_health_status",
    "Component health status (1=healthy, 0.5=degraded, 0=unhealthy)",
    ["component"],
)

# Component health check latency
component_health_check_duration_seconds = Histogram(
    "component_health_check_duration_seconds",
    "Component health check duration",
    ["component"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Overall health check duration
health_check_duration_seconds = Histogram(
    "health_check_duration_seconds",
    "Overall health check duration",
    ["check_type"],  # liveness, readiness
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0),
)

# Health check failures
health_check_failures_total = Counter(
    "health_check_failures_total",
    "Health check failures",
    ["component"],
)

# Health check total
health_checks_total = Counter(
    "health_checks_total",
    "Total health checks performed",
    ["check_type", "status"],  # status: healthy, degraded, unhealthy
)

# ========================================
# Week 3: Document Security Metrics
# ========================================

# Document access validations
document_validations_total = Counter(
    "document_validations_total",
    "Total document access validations",
    ["decision"],  # allow, deny, audit
)

# Document access by role
document_access_by_role = Counter(
    "document_access_by_role",
    "Document access attempts by role",
    ["role", "result"],  # result: allowed, denied
)

# Document access by tag
document_access_by_tag = Counter(
    "document_access_by_tag",
    "Document access attempts by tag",
    ["tag", "result"],
)

# Validation latency
document_validation_duration_seconds = Histogram(
    "document_validation_duration_seconds",
    "Document validation duration",
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05),
)

# Audit events
audit_events_total = Counter(
    "audit_events_total",
    "Total audit events logged",
    ["event_type"],  # access, denied, audit
)

# Blacklist/whitelist size
document_list_size = Gauge(
    "document_list_size",
    "Size of document lists",
    ["list_type"],  # whitelist, blacklist
)

# ========================================
# Week 3: Enhanced HTTP Metrics
# ========================================

# Active HTTP connections
http_requests_active = Gauge(
    "http_requests_active",
    "Number of active HTTP requests",
    ["method", "path"],
)

# HTTP request size
http_request_size_bytes = Histogram(
    "http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "path"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000),
)

# HTTP response size
http_response_size_bytes = Histogram(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "path"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000),
)

# HTTP errors by status code
http_errors_total = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["method", "path", "status_code"],
)


class Week3MetricsCollector:
    """
    Metrics collector for Week 3 observability features

    Provides helper methods for tracking:
    - Circuit breaker events
    - Health check results
    - Document security events
    - Enhanced HTTP metrics
    """

    # ========================================
    # Circuit Breaker Tracking
    # ========================================

    @staticmethod
    def track_circuit_breaker_state(service: str, state: str):
        """
        Track circuit breaker state

        Args:
            service: Service name (weaviate, opensearch, redis, gemini)
            state: Circuit state (closed, open, half_open)
        """
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state.lower(), 0)
        circuit_breaker_state.labels(service=service).set(state_value)

    @staticmethod
    def track_circuit_breaker_failure(service: str):
        """Track circuit breaker failure"""
        circuit_breaker_failures_total.labels(service=service).inc()

    @staticmethod
    def track_circuit_breaker_success(service: str):
        """Track circuit breaker success"""
        circuit_breaker_successes_total.labels(service=service).inc()

    @staticmethod
    def track_circuit_breaker_state_change(
        service: str, from_state: str, to_state: str, duration: float = None
    ):
        """
        Track circuit breaker state change

        Args:
            service: Service name
            from_state: Previous state
            to_state: New state
            duration: Time in previous state (seconds)
        """
        circuit_breaker_state_changes_total.labels(
            service=service, from_state=from_state, to_state=to_state
        ).inc()

        # Track open duration if moving from open state
        if from_state == "open" and duration:
            circuit_breaker_open_duration_seconds.labels(service=service).observe(
                duration
            )

    # ========================================
    # Health Check Tracking
    # ========================================

    @staticmethod
    def track_component_health(component: str, status: str, latency: float = None):
        """
        Track component health status

        Args:
            component: Component name (weaviate, opensearch, redis, filesystem)
            status: Health status (healthy, degraded, unhealthy)
            latency: Check latency in seconds
        """
        # Set status gauge
        status_value = {"healthy": 1.0, "degraded": 0.5, "unhealthy": 0.0}.get(
            status.lower(), 0.0
        )
        component_health_status.labels(component=component).set(status_value)

        # Track latency if provided
        if latency:
            component_health_check_duration_seconds.labels(component=component).observe(
                latency
            )

        # Track failure if unhealthy
        if status.lower() == "unhealthy":
            health_check_failures_total.labels(component=component).inc()

    @staticmethod
    def track_health_check(check_type: str, overall_status: str, duration: float):
        """
        Track overall health check

        Args:
            check_type: Check type (liveness, readiness)
            overall_status: Overall status (healthy, degraded, unhealthy)
            duration: Check duration in seconds
        """
        health_check_duration_seconds.labels(check_type=check_type).observe(duration)
        health_checks_total.labels(check_type=check_type, status=overall_status).inc()

    # ========================================
    # Document Security Tracking
    # ========================================

    @staticmethod
    def track_document_validation(
        decision: str, role: str = None, tag: str = None, duration: float = None
    ):
        """
        Track document validation

        Args:
            decision: Validation decision (allow, deny, audit)
            role: User role
            tag: Document tag
            duration: Validation duration in seconds
        """
        document_validations_total.labels(decision=decision).inc()

        if role:
            result = "allowed" if decision in ["allow", "audit"] else "denied"
            document_access_by_role.labels(role=role, result=result).inc()

        if tag:
            result = "allowed" if decision in ["allow", "audit"] else "denied"
            document_access_by_tag.labels(tag=tag, result=result).inc()

        if duration:
            document_validation_duration_seconds.observe(duration)

    @staticmethod
    def track_audit_event(event_type: str):
        """
        Track audit event

        Args:
            event_type: Event type (access, denied, audit)
        """
        audit_events_total.labels(event_type=event_type).inc()

    @staticmethod
    def update_document_list_sizes(whitelist_size: int, blacklist_size: int):
        """
        Update document list sizes

        Args:
            whitelist_size: Number of whitelisted documents
            blacklist_size: Number of blacklisted documents
        """
        document_list_size.labels(list_type="whitelist").set(whitelist_size)
        document_list_size.labels(list_type="blacklist").set(blacklist_size)

    # ========================================
    # Enhanced HTTP Tracking
    # ========================================

    @staticmethod
    def track_http_request_start(method: str, path: str):
        """Track start of HTTP request (increment active counter)"""
        http_requests_active.labels(method=method, path=path).inc()

    @staticmethod
    def track_http_request_end(method: str, path: str):
        """Track end of HTTP request (decrement active counter)"""
        http_requests_active.labels(method=method, path=path).dec()

    @staticmethod
    def track_http_sizes(
        method: str, path: str, request_size: int = None, response_size: int = None
    ):
        """
        Track HTTP request/response sizes

        Args:
            method: HTTP method
            path: Request path
            request_size: Request size in bytes
            response_size: Response size in bytes
        """
        if request_size:
            http_request_size_bytes.labels(method=method, path=path).observe(
                request_size
            )
        if response_size:
            http_response_size_bytes.labels(method=method, path=path).observe(
                response_size
            )

    @staticmethod
    def track_http_error(method: str, path: str, status_code: int):
        """
        Track HTTP error

        Args:
            method: HTTP method
            path: Request path
            status_code: HTTP status code
        """
        if status_code >= 400:
            http_errors_total.labels(
                method=method, path=path, status_code=str(status_code)
            ).inc()


# Global Week 3 metrics collector instance
week3_metrics = Week3MetricsCollector()


# ========================================
# Decorator for automatic metric tracking
# ========================================


def track_circuit_breaker_call(service: str):
    """
    Decorator to track circuit breaker protected calls

    Usage:
        @track_circuit_breaker_call("weaviate")
        def search_weaviate(query):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                week3_metrics.track_circuit_breaker_success(service)
                return result
            except Exception as e:
                week3_metrics.track_circuit_breaker_failure(service)
                raise

        return wrapper

    return decorator


logger.info("Week 3 metrics initialized")
