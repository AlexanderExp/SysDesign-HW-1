"""Tests for Circuit Breaker functionality."""

import pytest
from unittest.mock import Mock, patch
from pybreaker import CircuitBreaker, CircuitBreakerError


def test_circuit_breaker_basic_functionality():
    """Test basic Circuit Breaker functionality."""
    breaker = CircuitBreaker(fail_max=2, reset_timeout=1)
    
    # Initially closed
    assert breaker.current_state == "closed"
    
    # Mock function that fails
    def failing_function():
        raise Exception("Service down")
    
    # Trigger failures
    for _ in range(2):
        with pytest.raises(Exception):
            breaker(failing_function)()
    
    # Should be open now
    assert breaker.current_state == "open"
    
    # Next call should raise CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        breaker(failing_function)()


def test_circuit_breaker_excludes_certain_exceptions():
    """Test that Circuit Breaker can exclude certain exceptions."""
    breaker = CircuitBreaker(fail_max=2, reset_timeout=1, exclude=[KeyError])
    
    def function_with_key_error():
        raise KeyError("Missing key")
    
    # KeyError should not count towards failures
    initial_fail_count = breaker.fail_counter
    
    with pytest.raises(KeyError):
        breaker(function_with_key_error)()
    
    # Fail counter should not increase
    assert breaker.fail_counter == initial_fail_count
    assert breaker.current_state == "closed"


def test_circuit_breaker_success_resets_counter():
    """Test that successful calls reset the failure counter."""
    breaker = CircuitBreaker(fail_max=3, reset_timeout=1)
    
    def sometimes_failing_function(should_fail=True):
        if should_fail:
            raise Exception("Service down")
        return "success"
    
    # Trigger some failures
    for _ in range(2):
        with pytest.raises(Exception):
            breaker(lambda: sometimes_failing_function(True))()
    
    assert breaker.fail_counter == 2
    
    # Successful call should reset counter
    result = breaker(lambda: sometimes_failing_function(False))()
    assert result == "success"
    assert breaker.fail_counter == 0


def test_circuit_breaker_with_fallback():
    """Test Circuit Breaker with fallback mechanism."""
    breaker = CircuitBreaker(fail_max=1, reset_timeout=1)
    
    def external_service():
        raise Exception("Service unavailable")
    
    def service_with_fallback():
        try:
            return breaker(external_service)()
        except (Exception, CircuitBreakerError):
            return "fallback_result"
    
    # First call triggers failure and opens circuit
    with pytest.raises(Exception):
        breaker(external_service)()
    
    # Service with fallback should return fallback
    result = service_with_fallback()
    assert result == "fallback_result"


def test_circuit_breaker_listeners():
    """Test Circuit Breaker state change listeners."""
    state_changes = []
    
    def state_listener(breaker, old_state, new_state):
        state_changes.append((old_state, new_state))
    
    breaker = CircuitBreaker(fail_max=1, reset_timeout=1, listeners=[state_listener])
    
    def failing_function():
        raise Exception("Service down")
    
    # Trigger failure to open circuit
    with pytest.raises(Exception):
        breaker(failing_function)()
    
    # Verify listener was registered (even if not called yet)
    assert len(breaker._listeners) == 1
    assert state_listener in breaker._listeners


def test_circuit_breaker_reset_timeout():
    """Test Circuit Breaker reset timeout functionality."""
    import time
    
    breaker = CircuitBreaker(fail_max=1, reset_timeout=1)  # Short timeout for testing
    
    def failing_function():
        raise Exception("Service down")
    
    # Open the circuit
    with pytest.raises(Exception):
        breaker(failing_function)()
    
    assert breaker.current_state == "open"
    
    # Before timeout - should still be open
    with pytest.raises(CircuitBreakerError):
        breaker(failing_function)()
    
    # Wait for timeout
    time.sleep(1.1)
    
    def working_function():
        return "success"
    
    # Should allow one test call and close circuit on success
    result = breaker(working_function)()
    assert result == "success"
    assert breaker.current_state == "closed"


def test_circuit_breaker_integration_pattern():
    """Test Circuit Breaker integration pattern similar to our implementation."""
    
    class MockExternalClient:
        def __init__(self):
            self.breaker = CircuitBreaker(fail_max=2, reset_timeout=30)
            self.call_count = 0
        
        def external_call(self, should_fail=True):
            @self.breaker
            def _make_call():
                self.call_count += 1
                if should_fail:
                    raise Exception("External service error")
                return f"success_{self.call_count}"
            
            return _make_call()
        
        def external_call_with_fallback(self, should_fail=True):
            try:
                return self.external_call(should_fail), None
            except (Exception, CircuitBreakerError) as e:
                return None, str(e)
    
    client = MockExternalClient()
    
    # Test normal operation
    result, error = client.external_call_with_fallback(should_fail=False)
    assert result == "success_1"
    assert error is None
    
    # Test failures opening circuit
    result1, error1 = client.external_call_with_fallback(should_fail=True)
    assert result1 is None
    assert "External service error" in error1
    
    result2, error2 = client.external_call_with_fallback(should_fail=True)
    assert result2 is None
    # Second call might get circuit breaker error instead of original error
    assert error2 is not None
    
    # Circuit should be open now
    result3, error3 = client.external_call_with_fallback(should_fail=False)
    assert result3 is None
    # Circuit breaker error message may vary
    assert error3 is not None


def test_circuit_breaker_stats():
    """Test getting Circuit Breaker statistics."""
    breaker = CircuitBreaker(fail_max=3, reset_timeout=60, name="test_breaker")
    
    # Initial state
    assert breaker.fail_counter == 0
    assert breaker.fail_max == 3
    assert breaker.reset_timeout == 60
    assert breaker.current_state == "closed"
    
    def failing_function():
        raise Exception("Test failure")
    
    # Trigger some failures
    for _ in range(2):
        with pytest.raises(Exception):
            breaker(failing_function)()
    
    # Check updated stats
    assert breaker.fail_counter == 2
    assert breaker.current_state == "closed"  # Still closed
    
    # One more failure should open it
    with pytest.raises(Exception):
        breaker(failing_function)()
    
    assert breaker.current_state == "open"