"""Retry and backoff simulation for LocalZure Gateway.

This module provides test mode functionality to inject transient failures
and simulate Azure retry behavior for testing application retry logic.
"""

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FailurePattern(str, Enum):
    """Failure injection patterns."""

    RANDOM = "random"  # Random failures based on rate
    SEQUENTIAL = "sequential"  # Every Nth request fails
    BURST = "burst"  # Failures in bursts


class RetryAfterFormat(str, Enum):
    """Retry-After header format."""

    SECONDS = "seconds"  # Delay in seconds
    HTTP_DATE = "http_date"  # HTTP date format


@dataclass
class _TestModeConfig:
    """Configuration for test mode failure injection."""

    __test__ = False  # Tell pytest not to collect this class

    enabled: bool = False
    failure_rate: float = 0.0  # 0.0 to 1.0
    error_codes: List[int] = field(default_factory=lambda: [503])
    retry_after: int = 5  # seconds
    retry_after_format: RetryAfterFormat = RetryAfterFormat.SECONDS
    pattern: FailurePattern = FailurePattern.RANDOM
    burst_size: int = 3  # For burst pattern
    burst_interval: int = 10  # seconds between bursts
    duration: Optional[int] = None  # Duration in seconds (None = infinite)
    service_scope: Optional[str] = None  # Service name or None for global

    def __post_init__(self):
        """Validate configuration."""
        if not 0.0 <= self.failure_rate <= 1.0:
            raise ValueError("failure_rate must be between 0.0 and 1.0")
        if self.retry_after < 0:
            raise ValueError("retry_after must be non-negative")
        if not self.error_codes:
            self.error_codes = [503]
        # Validate error codes are in acceptable range
        for code in self.error_codes:
            if code not in (429, 500, 502, 503, 504):
                raise ValueError(
                    f"error_code {code} not supported. "
                    "Use 429, 500, 502, 503, or 504"
                )


# Public alias to avoid pytest collection warning
TestModeConfig = _TestModeConfig


@dataclass
class FailureInjectionResult:
    """Result of failure injection check."""

    should_fail: bool
    error_code: int
    retry_after: str
    retry_after_ms: Optional[int] = None
    reason: str = ""


class RetrySimulator:
    """Simulates Azure retry behavior and backoff patterns."""

    def __init__(self, global_config: Optional[_TestModeConfig] = None):
        """Initialize retry simulator.

        Args:
            global_config: Global test mode configuration
        """
        self.global_config = global_config or _TestModeConfig()
        self.service_configs: Dict[str, _TestModeConfig] = {}
        self._request_counter = 0
        self._last_burst_time = 0.0
        self._burst_count = 0
        self._start_time = time.time()
        self._random = random.Random()  # Separate instance for determinism

    def set_seed(self, seed: int) -> None:
        """Set random seed for deterministic failure injection.

        Args:
            seed: Random seed value
        """
        self._random.seed(seed)
        logger.debug(f"Set retry simulator seed to {seed}")

    def register_service_config(
        self, service_name: str, config: _TestModeConfig
    ) -> None:
        """Register test mode config for a specific service.

        Args:
            service_name: Name of the service
            config: Test mode configuration for the service
        """
        config.service_scope = service_name
        self.service_configs[service_name] = config
        logger.info(
            f"Registered test mode config for service: {service_name} "
            f"(failure_rate={config.failure_rate})"
        )

    def get_config(self, service_name: Optional[str] = None) -> _TestModeConfig:
        """Get applicable test mode configuration.

        Args:
            service_name: Service name to check for specific config

        Returns:
            Service-specific config if available, otherwise global config
        """
        if service_name and service_name in self.service_configs:
            return self.service_configs[service_name]
        return self.global_config

    def is_enabled(self, service_name: Optional[str] = None) -> bool:
        """Check if test mode is enabled.

        Args:
            service_name: Service name to check

        Returns:
            True if test mode is enabled for the service or globally
        """
        config = self.get_config(service_name)
        return config.enabled

    def check_failure(
        self,
        service_name: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> FailureInjectionResult:
        """Check if this request should fail based on test mode config.

        Args:
            service_name: Service handling the request
            request_id: Optional request ID for deterministic failure

        Returns:
            FailureInjectionResult with failure details
        """
        config = self.get_config(service_name)

        # If not enabled, no failure
        if not config.enabled:
            return FailureInjectionResult(
                should_fail=False,
                error_code=200,
                retry_after="",
                reason="test_mode_disabled",
            )

        # Check if duration has expired
        if config.duration is not None:
            elapsed = time.time() - self._start_time
            if elapsed > config.duration:
                return FailureInjectionResult(
                    should_fail=False,
                    error_code=200,
                    retry_after="",
                    reason="duration_expired",
                )

        # Increment counter
        self._request_counter += 1

        # Determine if this request should fail based on pattern
        should_fail = self._should_inject_failure(config, request_id)

        if not should_fail:
            return FailureInjectionResult(
                should_fail=False,
                error_code=200,
                retry_after="",
                reason="no_failure_injected",
            )

        # Select error code
        error_code = self._random.choice(config.error_codes)

        # Generate Retry-After header
        retry_after, retry_after_ms = self._generate_retry_after(config)

        logger.debug(
            f"Injecting failure: {error_code} "
            f"(pattern={config.pattern}, counter={self._request_counter})"
        )

        return FailureInjectionResult(
            should_fail=True,
            error_code=error_code,
            retry_after=retry_after,
            retry_after_ms=retry_after_ms,
            reason=f"pattern_{config.pattern.value}",
        )

    def _should_inject_failure(
        self, config: _TestModeConfig, request_id: Optional[str]
    ) -> bool:
        """Determine if failure should be injected based on pattern.

        Args:
            config: Test mode configuration
            request_id: Optional request ID for deterministic behavior

        Returns:
            True if failure should be injected
        """
        # pylint: disable=too-many-return-statements
        if config.pattern == FailurePattern.RANDOM:
            # Use request_id for deterministic random if provided
            if request_id:
                # Hash request_id to get deterministic random value
                hash_val = hash(request_id)
                return (hash_val % 100) < (config.failure_rate * 100)
            return self._random.random() < config.failure_rate

        elif config.pattern == FailurePattern.SEQUENTIAL:
            # Fail every Nth request based on failure rate
            if config.failure_rate == 0:
                return False
            interval = max(1, int(1.0 / config.failure_rate))
            return self._request_counter % interval == 0

        elif config.pattern == FailurePattern.BURST:
            # Fail in bursts
            current_time = time.time()
            time_since_burst = current_time - self._last_burst_time

            # Check if we should start a new burst
            if time_since_burst >= config.burst_interval:
                self._last_burst_time = current_time
                self._burst_count = 0

            # Inject failure if within burst
            if self._burst_count < config.burst_size:
                self._burst_count += 1
                return True

            return False

        return False

    def _generate_retry_after(
        self, config: _TestModeConfig
    ) -> Tuple[str, Optional[int]]:
        """Generate Retry-After header value.

        Args:
            config: Test mode configuration

        Returns:
            Tuple of (retry_after_header, retry_after_ms)
        """
        retry_after_ms = config.retry_after * 1000

        if config.retry_after_format == RetryAfterFormat.SECONDS:
            # Delay-seconds format
            return str(config.retry_after), retry_after_ms

        elif config.retry_after_format == RetryAfterFormat.HTTP_DATE:
            # HTTP-date format
            retry_time = datetime.now(timezone.utc) + timedelta(
                seconds=config.retry_after
            )
            # Format: "Fri, 31 Dec 2025 23:59:59 GMT"
            http_date = retry_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
            return http_date, retry_after_ms

        return str(config.retry_after), retry_after_ms

    def reset(self) -> None:
        """Reset simulator state."""
        self._request_counter = 0
        self._last_burst_time = 0.0
        self._burst_count = 0
        self._start_time = time.time()
        logger.debug("Reset retry simulator state")


def create_error_response(
    result: FailureInjectionResult,
) -> Dict[str, any]:
    """Create error response for injected failure.

    Args:
        result: Failure injection result

    Returns:
        Error response dict with status code, headers, and body
    """
    headers = {"Retry-After": result.retry_after}

    # Add x-ms-retry-after-ms header if available
    if result.retry_after_ms is not None:
        headers["x-ms-retry-after-ms"] = str(result.retry_after_ms)

    # Create error body based on status code
    if result.error_code == 429:
        error_body = {
            "error": {
                "code": "TooManyRequests",
                "message": "Rate limit exceeded. Please retry after the specified time.",
            }
        }
    elif result.error_code == 503:
        error_body = {
            "error": {
                "code": "ServiceUnavailable",
                "message": "The service is temporarily unavailable. Please retry after the specified time.",
            }
        }
    elif result.error_code == 500:
        error_body = {
            "error": {
                "code": "InternalServerError",
                "message": "The server encountered an internal error. Please retry.",
            }
        }
    elif result.error_code == 502:
        error_body = {
            "error": {
                "code": "BadGateway",
                "message": "The server received an invalid response. Please retry.",
            }
        }
    elif result.error_code == 504:
        error_body = {
            "error": {
                "code": "GatewayTimeout",
                "message": "The server timed out waiting for a response. Please retry.",
            }
        }
    else:
        error_body = {
            "error": {
                "code": "Error",
                "message": f"Request failed with status {result.error_code}",
            }
        }

    return {
        "status_code": result.error_code,
        "headers": headers,
        "body": error_body,
    }


def parse_test_mode_config(config_dict: Dict) -> _TestModeConfig:
    """Parse test mode configuration from dictionary.

    Args:
        config_dict: Configuration dictionary

    Returns:
        TestModeConfig object
    """
    # Extract and convert values
    enabled = config_dict.get("enabled", False)
    failure_rate = float(config_dict.get("failure_rate", 0.0))
    error_codes = config_dict.get("error_codes", [503])
    retry_after = int(config_dict.get("retry_after", 5))

    # Parse retry_after_format
    retry_format_str = config_dict.get("retry_after_format", "seconds")
    retry_after_format = (
        RetryAfterFormat.HTTP_DATE
        if retry_format_str == "http_date"
        else RetryAfterFormat.SECONDS
    )

    # Parse pattern
    pattern_str = config_dict.get("pattern", "random")
    pattern = FailurePattern(pattern_str)

    # Optional fields
    burst_size = int(config_dict.get("burst_size", 3))
    burst_interval = int(config_dict.get("burst_interval", 10))
    duration = config_dict.get("duration")
    if duration is not None:
        duration = int(duration)
    service_scope = config_dict.get("service_scope")

    return _TestModeConfig(
        enabled=enabled,
        failure_rate=failure_rate,
        error_codes=error_codes,
        retry_after=retry_after,
        retry_after_format=retry_after_format,
        pattern=pattern,
        burst_size=burst_size,
        burst_interval=burst_interval,
        duration=duration,
        service_scope=service_scope,
    )
