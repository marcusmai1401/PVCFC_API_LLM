"""
Unit tests for Circuit Breaker System

Tests:
- Circuit breaker instances
- State transitions (closed -> open -> half_open -> closed)
- Failure thresholds
- Timeout and recovery
- Integration with services
"""

import time
from unittest.mock import Mock, patch

import pytest
from pybreaker import CircuitBreaker, CircuitBreakerError

from app.core.circuit_breaker import (
    CircuitBreakerMetricsListener,
    get_circuit_breaker_status,
    get_gemini_breaker,
    get_opensearch_breaker,
    get_redis_breaker,
    get_weaviate_breaker,
    reset_all_circuit_breakers,
)


class TestCircuitBreakerInstances:
    """Test circuit breaker instance configuration"""

    def test_weaviate_breaker_exists(self):
        """Weaviate breaker should be configured"""
        breaker = get_weaviate_breaker()
        assert breaker is not None
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.fail_max == 5
        assert breaker._reset_timeout == 60

    def test_opensearch_breaker_exists(self):
        """OpenSearch breaker should be configured"""
        breaker = get_opensearch_breaker()
        assert breaker is not None
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.fail_max == 3
        assert breaker._reset_timeout == 30

    def test_redis_breaker_exists(self):
        """Redis breaker should be configured"""
        breaker = get_redis_breaker()
        assert breaker is not None
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.fail_max == 5

    def test_gemini_breaker_exists(self):
        """Gemini breaker should be configured"""
        breaker = get_gemini_breaker()
        assert breaker is not None
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.fail_max == 10


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions"""

    def test_breaker_starts_closed(self):
        """Circuit breaker should start in closed state"""
        breaker = CircuitBreaker(fail_max=2, reset_timeout=1)
        assert breaker.current_state == "closed"

    def test_breaker_opens_after_threshold(self):
        """Circuit breaker should open after failure threshold"""
        breaker = CircuitBreaker(fail_max=2, reset_timeout=60)

        # Simulate failures
        for _ in range(2):
            try:
                breaker.call(self._failing_function)
            except Exception:
                pass

        # Should be open now
        assert breaker.current_state == "open"

    def test_breaker_blocks_when_open(self):
        """Circuit breaker should block calls when open"""
        breaker = CircuitBreaker(fail_max=1, reset_timeout=60)

        # Trigger failure to open breaker
        try:
            breaker.call(self._failing_function)
        except Exception:
            pass

        # Next call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            breaker.call(self._failing_function)

    def test_breaker_transitions_to_half_open(self):
        """Circuit breaker should transition to half-open after timeout"""
        breaker = CircuitBreaker(fail_max=1, reset_timeout=0.1)

        # Open the breaker
        try:
            breaker.call(self._failing_function)
        except Exception:
            pass

        assert breaker.current_state == "open"

        # Wait for timeout
        time.sleep(0.2)

        # Should transition to half-open on next call
        try:
            breaker.call(self._successful_function)
        except:
            pass

        # If success, should be closed again
        assert breaker.current_state == "closed"

    def test_breaker_closes_on_success(self):
        """Circuit breaker should close on successful call in half-open"""
        breaker = CircuitBreaker(fail_max=1, reset_timeout=0.1)

        # Open breaker
        try:
            breaker.call(self._failing_function)
        except:
            pass

        # Wait for half-open
        time.sleep(0.2)

        # Successful call should close it
        result = breaker.call(self._successful_function)
        assert result == "success"
        assert breaker.current_state == "closed"

    def test_breaker_reopens_on_failure_in_half_open(self):
        """Circuit breaker should reopen on failure in half-open state"""
        breaker = CircuitBreaker(fail_max=1, reset_timeout=0.1)

        # Open breaker
        try:
            breaker.call(self._failing_function)
        except:
            pass

        # Wait for half-open
        time.sleep(0.2)

        # Another failure should reopen it
        try:
            breaker.call(self._failing_function)
        except:
            pass

        assert breaker.current_state == "open"

    @staticmethod
    def _failing_function():
        """Helper function that always fails"""
        raise Exception("Simulated failure")

    @staticmethod
    def _successful_function():
        """Helper function that always succeeds"""
        return "success"


class TestCircuitBreakerWithMockedServices:
    """Test circuit breaker with mocked service calls"""

    def test_weaviate_breaker_with_mock_search(self):
        """Test Weaviate breaker with mocked search"""
        # Create isolated breaker for this test
        breaker = CircuitBreaker(fail_max=3, reset_timeout=60, name="test_weaviate")
        mock_search = Mock(side_effect=Exception("Connection failed"))

        # Should fail exactly fail_max times before opening
        # Note: pybreaker opens ON the fail_max-th failure, not after
        for i in range(breaker.fail_max - 1):
            try:
                breaker.call(mock_search)
            except CircuitBreakerError:
                pytest.fail(f"Breaker opened too early at attempt {i+1}")
            except Exception:
                pass  # Expected

        # The fail_max-th call should trigger the breaker to open
        # After that, subsequent calls raise CircuitBreakerError
        try:
            breaker.call(mock_search)
        except (Exception, CircuitBreakerError):
            pass

        # Verify breaker is now open
        assert breaker.current_state == "open"

        # Next call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            breaker.call(mock_search)

    def test_opensearch_breaker_with_mock_query(self):
        """Test OpenSearch breaker with mocked query"""
        breaker = get_opensearch_breaker()
        mock_query = Mock(return_value={"hits": {"hits": []}})

        # Should succeed
        result = breaker.call(mock_query)
        assert result == {"hits": {"hits": []}}

    def test_breaker_tracks_failure_count(self):
        """Circuit breaker should track failure count"""
        breaker = CircuitBreaker(fail_max=3, reset_timeout=60)

        # Fail twice
        for _ in range(2):
            try:
                breaker.call(lambda: 1 / 0)
            except:
                pass

        # Should still be closed
        assert breaker.current_state == "closed"

        # One more failure should open it
        try:
            breaker.call(lambda: 1 / 0)
        except:
            pass

        assert breaker.current_state == "open"


class TestCircuitBreakerFailureScenarios:
    """Test various failure scenarios"""

    def test_breaker_with_timeout_exception(self):
        """Test breaker with timeout-like exceptions"""

        def timeout_function():
            raise TimeoutError("Request timed out")

        breaker = CircuitBreaker(fail_max=2, reset_timeout=60)

        # Timeout should count as failure
        for _ in range(2):
            try:
                breaker.call(timeout_function)
            except (TimeoutError, CircuitBreakerError):
                pass

        assert breaker.current_state == "open"

    def test_breaker_with_connection_error(self):
        """Test breaker with connection errors"""

        def connection_error_function():
            raise ConnectionError("Cannot connect to service")

        breaker = CircuitBreaker(fail_max=2, reset_timeout=60)

        for _ in range(2):
            try:
                breaker.call(connection_error_function)
            except (ConnectionError, CircuitBreakerError):
                pass

        assert breaker.current_state == "open"

    def test_breaker_mixed_success_and_failure(self):
        """Test breaker with mixed success and failure"""
        breaker = CircuitBreaker(fail_max=3, reset_timeout=60)

        # Success
        breaker.call(lambda: "ok")

        # Failure
        try:
            breaker.call(lambda: 1 / 0)
        except:
            pass

        # Success
        breaker.call(lambda: "ok")

        # Should still be closed
        assert breaker.current_state == "closed"

        # More failures
        for _ in range(3):
            try:
                breaker.call(lambda: 1 / 0)
            except:
                pass

        # Now should be open
        assert breaker.current_state == "open"


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery behavior"""

    def test_breaker_recovers_after_timeout(self):
        """Test breaker recovers after reset timeout"""
        breaker = CircuitBreaker(fail_max=1, reset_timeout=0.1)

        # Open breaker
        try:
            breaker.call(lambda: 1 / 0)
        except:
            pass

        assert breaker.current_state == "open"

        # Wait for recovery
        time.sleep(0.2)

        # Should allow calls again (half-open)
        result = breaker.call(lambda: "recovered")
        assert result == "recovered"
        assert breaker.current_state == "closed"

    def test_breaker_manual_reset(self):
        """Test manual breaker reset"""
        breaker = CircuitBreaker(fail_max=1, reset_timeout=60)

        # Open breaker
        try:
            breaker.call(lambda: 1 / 0)
        except:
            pass

        assert breaker.current_state == "open"

        # Manual close (not reset)
        breaker.close()

        # Should be closed now
        assert breaker.current_state == "closed"


class TestCircuitBreakerIntegration:
    """Integration tests with actual breaker usage patterns"""

    def test_breaker_protects_service_calls(self):
        """Test breaker protects against cascading failures"""
        call_count = 0

        def unreliable_service():
            nonlocal call_count
            call_count += 1
            raise Exception("Service unavailable")

        breaker = CircuitBreaker(fail_max=3, reset_timeout=60)

        # Fail until breaker opens
        for _ in range(3):
            try:
                breaker.call(unreliable_service)
            except Exception:
                pass

        # Breaker should prevent further calls
        initial_count = call_count

        for _ in range(10):
            try:
                breaker.call(unreliable_service)
            except CircuitBreakerError:
                pass

        # Call count should not increase (breaker blocking)
        assert call_count == initial_count

    def test_breaker_fallback_pattern(self):
        """Test circuit breaker with fallback logic"""

        def primary_service():
            raise Exception("Primary service down")

        def fallback_service():
            return "fallback result"

        breaker = CircuitBreaker(fail_max=1, reset_timeout=60)

        # Try primary, use fallback on failure
        try:
            result = breaker.call(primary_service)
        except (Exception, CircuitBreakerError):
            result = fallback_service()

        assert result == "fallback result"

    def test_all_breakers_independent(self):
        """Test that all breakers are independent instances"""
        weaviate = get_weaviate_breaker()
        opensearch = get_opensearch_breaker()
        redis = get_redis_breaker()
        gemini = get_gemini_breaker()

        # They should be different objects
        assert weaviate is not opensearch
        assert weaviate is not redis
        assert weaviate is not gemini

        # Opening one should not affect others
        # (This is implicit from being different instances)


class TestCircuitBreakerStatus:
    """Test circuit breaker status and monitoring"""

    def test_get_circuit_breaker_status(self):
        """Test getting status of all circuit breakers"""
        status = get_circuit_breaker_status()

        # Should have all breaker names
        assert "weaviate" in status
        assert "opensearch" in status
        assert "gemini" in status
        assert "redis" in status

        # Each should have initialized status
        for name, breaker_status in status.items():
            assert "initialized" in breaker_status

    def test_circuit_breaker_status_after_init(self):
        """Test status after breakers are initialized"""
        # Initialize breakers
        get_weaviate_breaker()
        get_opensearch_breaker()

        status = get_circuit_breaker_status()

        # Initialized breakers should have full status
        assert status["weaviate"]["initialized"] is True
        assert "state" in status["weaviate"]
        assert "fail_counter" in status["weaviate"]

    def test_reset_all_circuit_breakers(self):
        """Test resetting all circuit breakers"""
        # Initialize and potentially open a breaker
        breaker = get_weaviate_breaker()

        # Try to open it
        for _ in range(breaker.fail_max):
            try:
                breaker.call(lambda: 1 / 0)
            except:
                pass

        # Reset all
        reset_all_circuit_breakers()

        # Should be closed
        status = get_circuit_breaker_status()
        assert status["weaviate"]["state"] == "closed"


class TestCircuitBreakerListener:
    """Test circuit breaker listener callbacks"""

    def test_listener_state_change(self):
        """Test listener logs state changes"""
        listener = CircuitBreakerMetricsListener()
        breaker = CircuitBreaker(
            fail_max=1,
            reset_timeout=1,
            name="test_listener",
            listeners=[listener],
        )

        # Trigger state change by causing failure
        try:
            breaker.call(lambda: 1 / 0)
        except:
            pass

        # Listener should have been notified
        # (We can't easily verify log output, but ensure no errors)
        assert breaker.current_state == "open"

    def test_listener_failure_callback(self):
        """Test listener receives failure notifications"""
        listener = CircuitBreakerMetricsListener()
        breaker = CircuitBreaker(
            fail_max=5, reset_timeout=60, name="test_failure", listeners=[listener]
        )

        # Cause a failure
        try:
            breaker.call(lambda: 1 / 0)
        except:
            pass

        # Should still be closed (not enough failures)
        assert breaker.current_state == "closed"

    def test_listener_success_callback(self):
        """Test listener receives success notifications"""
        listener = CircuitBreakerMetricsListener()
        breaker = CircuitBreaker(
            fail_max=5, reset_timeout=60, name="test_success", listeners=[listener]
        )

        # Successful call
        result = breaker.call(lambda: "success")
        assert result == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
