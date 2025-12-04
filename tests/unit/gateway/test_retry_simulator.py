"""Tests for retry simulator."""

import pytest
from datetime import datetime, timezone
from localzure.gateway.retry_simulator import (
    RetrySimulator,
    TestModeConfig,
    FailurePattern,
    RetryAfterFormat,
    FailureInjectionResult,
    create_error_response,
    parse_test_mode_config,
)


class TestTestModeConfig:
    """Tests for TestModeConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TestModeConfig()
        assert config.enabled is False
        assert config.failure_rate == 0.0
        assert config.error_codes == [503]
        assert config.retry_after == 5
        assert config.retry_after_format == RetryAfterFormat.SECONDS
        assert config.pattern == FailurePattern.RANDOM
        assert config.burst_size == 3
        assert config.burst_interval == 10
        assert config.duration is None
        assert config.service_scope is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=0.3,
            error_codes=[429, 503],
            retry_after=10,
            retry_after_format=RetryAfterFormat.HTTP_DATE,
            pattern=FailurePattern.BURST,
            burst_size=5,
            burst_interval=20,
            duration=60,
            service_scope="storage",
        )
        assert config.enabled is True
        assert config.failure_rate == 0.3
        assert config.error_codes == [429, 503]
        assert config.retry_after == 10
        assert config.retry_after_format == RetryAfterFormat.HTTP_DATE
        assert config.pattern == FailurePattern.BURST
        assert config.burst_size == 5
        assert config.burst_interval == 20
        assert config.duration == 60
        assert config.service_scope == "storage"

    def test_invalid_failure_rate_high(self):
        """Test invalid failure rate > 1.0."""
        with pytest.raises(ValueError, match="failure_rate must be between"):
            TestModeConfig(failure_rate=1.5)

    def test_invalid_failure_rate_low(self):
        """Test invalid failure rate < 0.0."""
        with pytest.raises(ValueError, match="failure_rate must be between"):
            TestModeConfig(failure_rate=-0.1)

    def test_invalid_retry_after(self):
        """Test invalid retry_after < 0."""
        with pytest.raises(ValueError, match="retry_after must be non-negative"):
            TestModeConfig(retry_after=-1)

    def test_invalid_error_code(self):
        """Test invalid error code."""
        with pytest.raises(ValueError, match="error_code.*not supported"):
            TestModeConfig(error_codes=[400])

    def test_empty_error_codes_defaults_to_503(self):
        """Test empty error codes defaults to [503]."""
        config = TestModeConfig(error_codes=[])
        assert config.error_codes == [503]

    def test_all_valid_error_codes(self):
        """Test all supported error codes."""
        config = TestModeConfig(error_codes=[429, 500, 502, 503, 504])
        assert config.error_codes == [429, 500, 502, 503, 504]


class TestRetrySimulator:
    """Tests for RetrySimulator."""

    def test_default_initialization(self):
        """Test default initialization."""
        simulator = RetrySimulator()
        assert simulator.global_config.enabled is False
        assert len(simulator.service_configs) == 0
        assert simulator._request_counter == 0

    def test_initialization_with_config(self):
        """Test initialization with global config."""
        config = TestModeConfig(enabled=True, failure_rate=0.5)
        simulator = RetrySimulator(global_config=config)
        assert simulator.global_config.enabled is True
        assert simulator.global_config.failure_rate == 0.5

    def test_register_service_config(self):
        """Test registering service-specific config."""
        simulator = RetrySimulator()
        config = TestModeConfig(enabled=True, failure_rate=0.3)
        simulator.register_service_config("storage", config)

        assert "storage" in simulator.service_configs
        assert simulator.service_configs["storage"].enabled is True
        assert simulator.service_configs["storage"].service_scope == "storage"

    def test_get_config_service_specific(self):
        """Test getting service-specific config."""
        simulator = RetrySimulator()
        service_config = TestModeConfig(enabled=True, failure_rate=0.8)
        simulator.register_service_config("storage", service_config)

        config = simulator.get_config("storage")
        assert config.failure_rate == 0.8

    def test_get_config_global_fallback(self):
        """Test getting config falls back to global."""
        global_config = TestModeConfig(enabled=True, failure_rate=0.5)
        simulator = RetrySimulator(global_config=global_config)

        config = simulator.get_config("unknown_service")
        assert config.failure_rate == 0.5

    def test_is_enabled_global(self):
        """Test is_enabled with global config."""
        config = TestModeConfig(enabled=True)
        simulator = RetrySimulator(global_config=config)
        assert simulator.is_enabled() is True

    def test_is_enabled_service_specific(self):
        """Test is_enabled with service-specific config."""
        simulator = RetrySimulator()
        config = TestModeConfig(enabled=True)
        simulator.register_service_config("storage", config)

        assert simulator.is_enabled("storage") is True
        assert simulator.is_enabled("other_service") is False

    def test_is_enabled_default_disabled(self):
        """Test is_enabled returns False by default."""
        simulator = RetrySimulator()
        assert simulator.is_enabled() is False

    def test_check_failure_disabled(self):
        """Test check_failure when disabled."""
        simulator = RetrySimulator()
        result = simulator.check_failure()

        assert result.should_fail is False
        assert result.error_code == 200
        assert result.reason == "test_mode_disabled"

    def test_check_failure_random_pattern(self):
        """Test check_failure with random pattern."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=1.0,  # Always fail
            pattern=FailurePattern.RANDOM,
        )
        simulator = RetrySimulator(global_config=config)
        simulator.set_seed(42)

        result = simulator.check_failure()
        assert result.should_fail is True
        assert result.error_code in [503]

    def test_check_failure_random_pattern_never(self):
        """Test check_failure with random pattern at 0% rate."""
        config = TestModeConfig(
            enabled=True, failure_rate=0.0, pattern=FailurePattern.RANDOM
        )
        simulator = RetrySimulator(global_config=config)

        result = simulator.check_failure()
        assert result.should_fail is False

    def test_check_failure_sequential_pattern(self):
        """Test check_failure with sequential pattern."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=0.5,  # Every 2nd request fails
            pattern=FailurePattern.SEQUENTIAL,
        )
        simulator = RetrySimulator(global_config=config)

        # First request should fail (counter=1, 1 % 2 == 1, but wait...)
        # interval = 1/0.5 = 2, counter % 2 == 0 means fail
        result1 = simulator.check_failure()  # counter=1, 1%2=1, no fail
        result2 = simulator.check_failure()  # counter=2, 2%2=0, fail
        result3 = simulator.check_failure()  # counter=3, 3%2=1, no fail
        result4 = simulator.check_failure()  # counter=4, 4%2=0, fail

        assert result1.should_fail is False
        assert result2.should_fail is True
        assert result3.should_fail is False
        assert result4.should_fail is True

    def test_check_failure_burst_pattern(self):
        """Test check_failure with burst pattern."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=0.5,
            pattern=FailurePattern.BURST,
            burst_size=2,
            burst_interval=1,
        )
        simulator = RetrySimulator(global_config=config)

        # First burst: 2 failures
        result1 = simulator.check_failure()
        result2 = simulator.check_failure()
        result3 = simulator.check_failure()

        assert result1.should_fail is True
        assert result2.should_fail is True
        assert result3.should_fail is False

        # Wait for next burst
        import time

        time.sleep(1.1)
        result4 = simulator.check_failure()
        assert result4.should_fail is True

    def test_check_failure_with_duration(self):
        """Test check_failure respects duration."""
        config = TestModeConfig(
            enabled=True, failure_rate=1.0, duration=0  # Immediate expiry
        )
        simulator = RetrySimulator(global_config=config)

        import time

        time.sleep(0.1)  # Ensure duration expires

        result = simulator.check_failure()
        assert result.should_fail is False
        assert result.reason == "duration_expired"

    def test_check_failure_multiple_error_codes(self):
        """Test check_failure with multiple error codes."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=1.0,
            error_codes=[429, 500, 503],
            pattern=FailurePattern.RANDOM,
        )
        simulator = RetrySimulator(global_config=config)
        simulator.set_seed(42)

        # Make multiple requests to see variety of error codes
        error_codes = set()
        for _ in range(10):
            result = simulator.check_failure()
            if result.should_fail:
                error_codes.add(result.error_code)

        # Should see at least one error code
        assert len(error_codes) > 0
        assert all(code in [429, 500, 503] for code in error_codes)

    def test_generate_retry_after_seconds(self):
        """Test generating Retry-After in seconds format."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=1.0,
            retry_after=10,
            retry_after_format=RetryAfterFormat.SECONDS,
        )
        simulator = RetrySimulator(global_config=config)

        result = simulator.check_failure()
        assert result.retry_after == "10"
        assert result.retry_after_ms == 10000

    def test_generate_retry_after_http_date(self):
        """Test generating Retry-After in HTTP-date format."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=1.0,
            retry_after=5,
            retry_after_format=RetryAfterFormat.HTTP_DATE,
        )
        simulator = RetrySimulator(global_config=config)

        result = simulator.check_failure()
        # Verify format: "Fri, 31 Dec 2025 23:59:59 GMT"
        assert "GMT" in result.retry_after
        assert result.retry_after_ms == 5000

        # Parse and verify it's in the future
        from datetime import datetime, timezone

        retry_time = datetime.strptime(result.retry_after, "%a, %d %b %Y %H:%M:%S %Z")
        # Replace naive datetime with UTC timezone for comparison
        retry_time = retry_time.replace(tzinfo=timezone.utc)
        assert retry_time > datetime.now(timezone.utc)

    def test_deterministic_failure_with_request_id(self):
        """Test deterministic failure injection with request_id."""
        config = TestModeConfig(
            enabled=True, failure_rate=0.5, pattern=FailurePattern.RANDOM
        )
        simulator = RetrySimulator(global_config=config)

        # Same request_id should produce same result
        result1 = simulator.check_failure(request_id="test-123")
        result2 = simulator.check_failure(request_id="test-123")

        assert result1.should_fail == result2.should_fail

    def test_set_seed(self):
        """Test setting random seed for deterministic behavior."""
        config = TestModeConfig(
            enabled=True, failure_rate=0.5, pattern=FailurePattern.RANDOM
        )

        # Two simulators with same seed should produce same sequence
        simulator1 = RetrySimulator(global_config=config)
        simulator1.set_seed(42)

        simulator2 = RetrySimulator(global_config=config)
        simulator2.set_seed(42)

        results1 = [simulator1.check_failure().should_fail for _ in range(10)]
        results2 = [simulator2.check_failure().should_fail for _ in range(10)]

        assert results1 == results2

    def test_reset(self):
        """Test resetting simulator state."""
        config = TestModeConfig(
            enabled=True, failure_rate=1.0, pattern=FailurePattern.SEQUENTIAL
        )
        simulator = RetrySimulator(global_config=config)

        # Make some requests
        simulator.check_failure()
        simulator.check_failure()
        assert simulator._request_counter == 2

        # Reset
        simulator.reset()
        assert simulator._request_counter == 0


class TestCreateErrorResponse:
    """Tests for create_error_response."""

    def test_create_429_response(self):
        """Test creating 429 error response."""
        result = FailureInjectionResult(
            should_fail=True,
            error_code=429,
            retry_after="10",
            retry_after_ms=10000,
            reason="rate_limit",
        )

        response = create_error_response(result)

        assert response["status_code"] == 429
        assert response["headers"]["Retry-After"] == "10"
        assert response["headers"]["x-ms-retry-after-ms"] == "10000"
        assert response["body"]["error"]["code"] == "TooManyRequests"

    def test_create_503_response(self):
        """Test creating 503 error response."""
        result = FailureInjectionResult(
            should_fail=True,
            error_code=503,
            retry_after="5",
            retry_after_ms=5000,
            reason="service_unavailable",
        )

        response = create_error_response(result)

        assert response["status_code"] == 503
        assert response["headers"]["Retry-After"] == "5"
        assert response["body"]["error"]["code"] == "ServiceUnavailable"

    def test_create_500_response(self):
        """Test creating 500 error response."""
        result = FailureInjectionResult(
            should_fail=True,
            error_code=500,
            retry_after="3",
            retry_after_ms=3000,
            reason="internal_error",
        )

        response = create_error_response(result)

        assert response["status_code"] == 500
        assert response["body"]["error"]["code"] == "InternalServerError"

    def test_create_502_response(self):
        """Test creating 502 error response."""
        result = FailureInjectionResult(
            should_fail=True, error_code=502, retry_after="5", reason="bad_gateway"
        )

        response = create_error_response(result)

        assert response["status_code"] == 502
        assert response["body"]["error"]["code"] == "BadGateway"

    def test_create_504_response(self):
        """Test creating 504 error response."""
        result = FailureInjectionResult(
            should_fail=True, error_code=504, retry_after="8", reason="timeout"
        )

        response = create_error_response(result)

        assert response["status_code"] == 504
        assert response["body"]["error"]["code"] == "GatewayTimeout"

    def test_create_response_with_http_date(self):
        """Test creating response with HTTP-date format."""
        result = FailureInjectionResult(
            should_fail=True,
            error_code=429,
            retry_after="Fri, 31 Dec 2025 23:59:59 GMT",
            retry_after_ms=10000,
            reason="rate_limit",
        )

        response = create_error_response(result)

        assert "GMT" in response["headers"]["Retry-After"]
        assert response["headers"]["x-ms-retry-after-ms"] == "10000"

    def test_create_response_without_retry_after_ms(self):
        """Test creating response without retry_after_ms."""
        result = FailureInjectionResult(
            should_fail=True, error_code=503, retry_after="5", reason="service_down"
        )

        response = create_error_response(result)

        assert "x-ms-retry-after-ms" not in response["headers"]


class TestParseTestModeConfig:
    """Tests for parse_test_mode_config."""

    def test_parse_minimal_config(self):
        """Test parsing minimal configuration."""
        config_dict = {"enabled": True}

        config = parse_test_mode_config(config_dict)

        assert config.enabled is True
        assert config.failure_rate == 0.0
        assert config.error_codes == [503]

    def test_parse_full_config(self):
        """Test parsing full configuration."""
        config_dict = {
            "enabled": True,
            "failure_rate": 0.3,
            "error_codes": [429, 503],
            "retry_after": 10,
            "retry_after_format": "http_date",
            "pattern": "burst",
            "burst_size": 5,
            "burst_interval": 20,
            "duration": 60,
            "service_scope": "storage",
        }

        config = parse_test_mode_config(config_dict)

        assert config.enabled is True
        assert config.failure_rate == 0.3
        assert config.error_codes == [429, 503]
        assert config.retry_after == 10
        assert config.retry_after_format == RetryAfterFormat.HTTP_DATE
        assert config.pattern == FailurePattern.BURST
        assert config.burst_size == 5
        assert config.burst_interval == 20
        assert config.duration == 60
        assert config.service_scope == "storage"

    def test_parse_config_with_defaults(self):
        """Test parsing with defaults."""
        config_dict = {}

        config = parse_test_mode_config(config_dict)

        assert config.enabled is False
        assert config.failure_rate == 0.0
        assert config.pattern == FailurePattern.RANDOM

    def test_parse_config_patterns(self):
        """Test parsing different patterns."""
        for pattern in ["random", "sequential", "burst"]:
            config_dict = {"pattern": pattern}
            config = parse_test_mode_config(config_dict)
            assert config.pattern.value == pattern

    def test_parse_config_retry_formats(self):
        """Test parsing different retry_after formats."""
        # Seconds format
        config1 = parse_test_mode_config({"retry_after_format": "seconds"})
        assert config1.retry_after_format == RetryAfterFormat.SECONDS

        # HTTP date format
        config2 = parse_test_mode_config({"retry_after_format": "http_date"})
        assert config2.retry_after_format == RetryAfterFormat.HTTP_DATE


class TestEndToEndScenarios:
    """End-to-end test scenarios."""

    def test_rate_limiting_scenario(self):
        """Test rate limiting scenario with 429 errors."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=1.0,
            error_codes=[429],
            retry_after=10,
            retry_after_format=RetryAfterFormat.SECONDS,
        )
        simulator = RetrySimulator(global_config=config)

        result = simulator.check_failure()
        response = create_error_response(result)

        assert response["status_code"] == 429
        assert response["headers"]["Retry-After"] == "10"
        assert "TooManyRequests" in str(response["body"])

    def test_service_unavailable_scenario(self):
        """Test service unavailable scenario."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=1.0,
            error_codes=[503],
            retry_after=5,
            retry_after_format=RetryAfterFormat.HTTP_DATE,
        )
        simulator = RetrySimulator(global_config=config)

        result = simulator.check_failure()
        response = create_error_response(result)

        assert response["status_code"] == 503
        assert "GMT" in response["headers"]["Retry-After"]

    def test_per_service_test_mode(self):
        """Test per-service test mode configuration."""
        global_config = TestModeConfig(enabled=False)
        simulator = RetrySimulator(global_config=global_config)

        # Enable test mode only for storage service
        storage_config = TestModeConfig(enabled=True, failure_rate=1.0)
        simulator.register_service_config("storage", storage_config)

        # Storage should fail
        storage_result = simulator.check_failure(service_name="storage")
        assert storage_result.should_fail is True

        # Other services should not fail
        queue_result = simulator.check_failure(service_name="queue")
        assert queue_result.should_fail is False

    def test_mixed_error_codes_scenario(self):
        """Test scenario with mixed error codes."""
        config = TestModeConfig(
            enabled=True,
            failure_rate=1.0,
            error_codes=[500, 502, 503, 504],
            pattern=FailurePattern.RANDOM,
        )
        simulator = RetrySimulator(global_config=config)
        simulator.set_seed(123)

        # Collect error codes from multiple requests
        error_codes = []
        for _ in range(20):
            result = simulator.check_failure()
            if result.should_fail:
                error_codes.append(result.error_code)

        # Should see server errors
        assert all(code in [500, 502, 503, 504] for code in error_codes)
        assert len(error_codes) > 0
