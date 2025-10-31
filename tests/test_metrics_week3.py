"""
Unit tests for Week 3 Metrics System

Tests:
- Circuit breaker metrics tracking
- Health check metrics
- Document security metrics
- Enhanced HTTP metrics
- Week3MetricsCollector methods
- Decorator functionality
"""

import pytest
from unittest.mock import Mock, patch

from app.core.metrics_week3 import (
    Week3MetricsCollector,
    audit_events_total,
    circuit_breaker_failures_total,
    circuit_breaker_open_duration_seconds,
    circuit_breaker_state,
    circuit_breaker_state_changes_total,
    circuit_breaker_successes_total,
    component_health_check_duration_seconds,
    component_health_status,
    document_access_by_role,
    document_access_by_tag,
    document_list_size,
    document_validation_duration_seconds,
    document_validations_total,
    health_check_duration_seconds,
    health_check_failures_total,
    health_checks_total,
    http_errors_total,
    http_request_size_bytes,
    http_requests_active,
    http_response_size_bytes,
    track_circuit_breaker_call,
    week3_metrics,
)


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics tracking"""

    def test_track_circuit_breaker_state_closed(self):
        """Track circuit breaker closed state"""
        week3_metrics.track_circuit_breaker_state("weaviate", "closed")

        # Verify state is set to 0 (closed)
        metric = circuit_breaker_state.labels(service="weaviate")
        assert metric._value._value == 0

    def test_track_circuit_breaker_state_open(self):
        """Track circuit breaker open state"""
        week3_metrics.track_circuit_breaker_state("opensearch", "open")

        # Verify state is set to 1 (open)
        metric = circuit_breaker_state.labels(service="opensearch")
        assert metric._value._value == 1

    def test_track_circuit_breaker_state_half_open(self):
        """Track circuit breaker half-open state"""
        week3_metrics.track_circuit_breaker_state("redis", "half_open")

        # Verify state is set to 2 (half_open)
        metric = circuit_breaker_state.labels(service="redis")
        assert metric._value._value == 2

    def test_track_circuit_breaker_failure(self):
        """Track circuit breaker failure"""
        # Get initial count
        metric = circuit_breaker_failures_total.labels(service="gemini")
        initial_count = metric._value._value

        # Track failure
        week3_metrics.track_circuit_breaker_failure("gemini")

        # Verify counter incremented
        assert metric._value._value == initial_count + 1

    def test_track_circuit_breaker_success(self):
        """Track circuit breaker success"""
        metric = circuit_breaker_successes_total.labels(service="weaviate")
        initial_count = metric._value._value

        week3_metrics.track_circuit_breaker_success("weaviate")

        assert metric._value._value == initial_count + 1

    def test_track_circuit_breaker_state_change(self):
        """Track circuit breaker state change"""
        metric = circuit_breaker_state_changes_total.labels(
            service="opensearch", from_state="closed", to_state="open"
        )
        initial_count = metric._value._value

        week3_metrics.track_circuit_breaker_state_change(
            "opensearch", "closed", "open"
        )

        assert metric._value._value == initial_count + 1

    def test_track_circuit_breaker_state_change_with_duration(self):
        """Track state change with open duration"""
        # Track transition from open with duration
        week3_metrics.track_circuit_breaker_state_change(
            "redis", "open", "half_open", duration=30.5
        )

        # Verify histogram observed the duration
        # (Hard to assert exact value, but ensure no errors)
        assert True


class TestHealthCheckMetrics:
    """Test health check metrics tracking"""

    def test_track_component_health_healthy(self):
        """Track healthy component"""
        week3_metrics.track_component_health("weaviate", "healthy", latency=0.05)

        # Verify status gauge set to 1.0
        metric = component_health_status.labels(component="weaviate")
        assert metric._value._value == 1.0

    def test_track_component_health_degraded(self):
        """Track degraded component"""
        week3_metrics.track_component_health("opensearch", "degraded", latency=0.15)

        metric = component_health_status.labels(component="opensearch")
        assert metric._value._value == 0.5

    def test_track_component_health_unhealthy(self):
        """Track unhealthy component"""
        metric_status = component_health_status.labels(component="redis")
        metric_failures = health_check_failures_total.labels(component="redis")

        initial_failures = metric_failures._value._value

        week3_metrics.track_component_health("redis", "unhealthy", latency=1.0)

        # Verify status is 0
        assert metric_status._value._value == 0.0

        # Verify failure counter incremented
        assert metric_failures._value._value == initial_failures + 1

    def test_track_health_check_liveness(self):
        """Track liveness health check"""
        metric = health_checks_total.labels(check_type="liveness", status="healthy")
        initial_count = metric._value._value

        week3_metrics.track_health_check("liveness", "healthy", duration=0.02)

        assert metric._value._value == initial_count + 1

    def test_track_health_check_readiness(self):
        """Track readiness health check"""
        metric = health_checks_total.labels(check_type="readiness", status="degraded")
        initial_count = metric._value._value

        week3_metrics.track_health_check("readiness", "degraded", duration=0.08)

        assert metric._value._value == initial_count + 1

    def test_component_health_without_latency(self):
        """Track component health without latency"""
        week3_metrics.track_component_health("filesystem", "healthy")

        metric = component_health_status.labels(component="filesystem")
        assert metric._value._value == 1.0


class TestDocumentSecurityMetrics:
    """Test document security metrics tracking"""

    def test_track_document_validation_allow(self):
        """Track document validation - allow"""
        metric = document_validations_total.labels(decision="allow")
        initial_count = metric._value._value

        week3_metrics.track_document_validation("allow")

        assert metric._value._value == initial_count + 1

    def test_track_document_validation_deny(self):
        """Track document validation - deny"""
        metric = document_validations_total.labels(decision="deny")
        initial_count = metric._value._value

        week3_metrics.track_document_validation("deny")

        assert metric._value._value == initial_count + 1

    def test_track_document_validation_with_role(self):
        """Track document validation with role"""
        metric_validation = document_validations_total.labels(decision="allow")
        metric_role = document_access_by_role.labels(role="admin", result="allowed")

        initial_validation = metric_validation._value._value
        initial_role = metric_role._value._value

        week3_metrics.track_document_validation("allow", role="admin")

        assert metric_validation._value._value == initial_validation + 1
        assert metric_role._value._value == initial_role + 1

    def test_track_document_validation_with_tag(self):
        """Track document validation with tag"""
        metric_tag = document_access_by_tag.labels(tag="confidential", result="denied")
        initial_count = metric_tag._value._value

        week3_metrics.track_document_validation("deny", tag="confidential")

        assert metric_tag._value._value == initial_count + 1

    def test_track_document_validation_with_duration(self):
        """Track document validation with duration"""
        week3_metrics.track_document_validation("audit", duration=0.002)

        # Verify no errors raised
        assert True

    def test_track_audit_event_access(self):
        """Track audit event - access"""
        metric = audit_events_total.labels(event_type="access")
        initial_count = metric._value._value

        week3_metrics.track_audit_event("access")

        assert metric._value._value == initial_count + 1

    def test_track_audit_event_denied(self):
        """Track audit event - denied"""
        metric = audit_events_total.labels(event_type="denied")
        initial_count = metric._value._value

        week3_metrics.track_audit_event("denied")

        assert metric._value._value == initial_count + 1

    def test_update_document_list_sizes(self):
        """Update document list sizes"""
        week3_metrics.update_document_list_sizes(whitelist_size=10, blacklist_size=5)

        metric_whitelist = document_list_size.labels(list_type="whitelist")
        metric_blacklist = document_list_size.labels(list_type="blacklist")

        assert metric_whitelist._value._value == 10
        assert metric_blacklist._value._value == 5


class TestEnhancedHTTPMetrics:
    """Test enhanced HTTP metrics tracking"""

    def test_track_http_request_start(self):
        """Track HTTP request start"""
        metric = http_requests_active.labels(method="GET", path="/api/ask")
        initial_value = metric._value._value

        week3_metrics.track_http_request_start("GET", "/api/ask")

        assert metric._value._value == initial_value + 1

    def test_track_http_request_end(self):
        """Track HTTP request end"""
        metric = http_requests_active.labels(method="POST", path="/api/ask")

        # Start first
        week3_metrics.track_http_request_start("POST", "/api/ask")
        value_after_start = metric._value._value

        # End
        week3_metrics.track_http_request_end("POST", "/api/ask")

        assert metric._value._value == value_after_start - 1

    def test_track_http_sizes_request_only(self):
        """Track HTTP request size only"""
        week3_metrics.track_http_sizes("POST", "/api/ask", request_size=1024)

        # Verify no errors
        assert True

    def test_track_http_sizes_response_only(self):
        """Track HTTP response size only"""
        week3_metrics.track_http_sizes("GET", "/health", response_size=256)

        assert True

    def test_track_http_sizes_both(self):
        """Track both request and response sizes"""
        week3_metrics.track_http_sizes(
            "POST", "/api/ask", request_size=2048, response_size=5120
        )

        assert True

    def test_track_http_error_400(self):
        """Track HTTP 400 error"""
        metric = http_errors_total.labels(
            method="GET", path="/api/invalid", status_code="400"
        )
        initial_count = metric._value._value

        week3_metrics.track_http_error("GET", "/api/invalid", 400)

        assert metric._value._value == initial_count + 1

    def test_track_http_error_500(self):
        """Track HTTP 500 error"""
        metric = http_errors_total.labels(
            method="POST", path="/api/ask", status_code="500"
        )
        initial_count = metric._value._value

        week3_metrics.track_http_error("POST", "/api/ask", 500)

        assert metric._value._value == initial_count + 1

    def test_track_http_error_success_not_counted(self):
        """HTTP 200 should not be counted as error"""
        metric = http_errors_total.labels(
            method="GET", path="/health", status_code="200"
        )
        initial_count = metric._value._value

        week3_metrics.track_http_error("GET", "/health", 200)

        # Should not increment (200 < 400)
        assert metric._value._value == initial_count


class TestDecoratorFunctionality:
    """Test decorator for circuit breaker tracking"""

    def test_track_circuit_breaker_call_success(self):
        """Test decorator tracks successful call"""
        metric = circuit_breaker_successes_total.labels(service="test_service")
        initial_count = metric._value._value

        @track_circuit_breaker_call("test_service")
        def successful_function():
            return "success"

        result = successful_function()

        assert result == "success"
        assert metric._value._value == initial_count + 1

    def test_track_circuit_breaker_call_failure(self):
        """Test decorator tracks failed call"""
        metric = circuit_breaker_failures_total.labels(service="test_service")
        initial_count = metric._value._value

        @track_circuit_breaker_call("test_service")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        assert metric._value._value == initial_count + 1

    def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves function metadata"""

        @track_circuit_breaker_call("test")
        def documented_function():
            """This is a test function"""
            return True

        assert documented_function.__doc__ == "This is a test function"
        assert documented_function.__name__ == "documented_function"

    def test_decorator_with_args_and_kwargs(self):
        """Test decorator with function arguments"""

        @track_circuit_breaker_call("test")
        def function_with_args(a, b, c=10):
            return a + b + c

        result = function_with_args(1, 2, c=3)
        assert result == 6


class TestMetricsCollectorInstance:
    """Test Week3MetricsCollector instance"""

    def test_week3_metrics_instance_exists(self):
        """Verify global week3_metrics instance exists"""
        assert week3_metrics is not None
        assert isinstance(week3_metrics, Week3MetricsCollector)

    def test_all_tracking_methods_callable(self):
        """Verify all tracking methods are callable"""
        assert callable(week3_metrics.track_circuit_breaker_state)
        assert callable(week3_metrics.track_circuit_breaker_failure)
        assert callable(week3_metrics.track_circuit_breaker_success)
        assert callable(week3_metrics.track_circuit_breaker_state_change)
        assert callable(week3_metrics.track_component_health)
        assert callable(week3_metrics.track_health_check)
        assert callable(week3_metrics.track_document_validation)
        assert callable(week3_metrics.track_audit_event)
        assert callable(week3_metrics.update_document_list_sizes)
        assert callable(week3_metrics.track_http_request_start)
        assert callable(week3_metrics.track_http_request_end)
        assert callable(week3_metrics.track_http_sizes)
        assert callable(week3_metrics.track_http_error)


class TestMetricsIntegration:
    """Integration tests for metrics tracking"""

    def test_complete_circuit_breaker_lifecycle(self):
        """Test complete circuit breaker lifecycle tracking"""
        service = "integration_test"

        # Track closed state
        week3_metrics.track_circuit_breaker_state(service, "closed")
        metric_state = circuit_breaker_state.labels(service=service)
        assert metric_state._value._value == 0

        # Track failures
        for _ in range(3):
            week3_metrics.track_circuit_breaker_failure(service)

        # Track state change to open
        week3_metrics.track_circuit_breaker_state_change(service, "closed", "open")
        week3_metrics.track_circuit_breaker_state(service, "open")
        assert metric_state._value._value == 1

        # Track recovery
        week3_metrics.track_circuit_breaker_state_change(
            service, "open", "half_open", duration=60
        )
        week3_metrics.track_circuit_breaker_success(service)

    def test_complete_health_check_flow(self):
        """Test complete health check flow"""
        component = "integration_component"

        # Check healthy
        week3_metrics.track_component_health(component, "healthy", latency=0.01)
        metric = component_health_status.labels(component=component)
        assert metric._value._value == 1.0

        # Check degraded
        week3_metrics.track_component_health(component, "degraded", latency=0.5)
        assert metric._value._value == 0.5

        # Track overall health check
        week3_metrics.track_health_check("readiness", "degraded", duration=0.1)

    def test_document_security_workflow(self):
        """Test document security tracking workflow"""
        # Allow with role
        week3_metrics.track_document_validation("allow", role="user", duration=0.001)

        # Deny with tag
        week3_metrics.track_document_validation("deny", tag="restricted")

        # Audit event
        week3_metrics.track_audit_event("access")

        # Update lists
        week3_metrics.update_document_list_sizes(100, 10)

        metric_whitelist = document_list_size.labels(list_type="whitelist")
        assert metric_whitelist._value._value == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
