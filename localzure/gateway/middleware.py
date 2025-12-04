"""FastAPI middleware for LocalZure Gateway.

This module integrates all gateway components into FastAPI middleware
for automatic request processing.
"""

from typing import Callable, Optional, Dict, Any
from datetime import datetime, timezone
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .hostname_mapper import HostnameMapper, MappingResult
from .rate_limiter import RateLimiter, RateLimitRule, RateLimitScope
from .circuit_breaker import CircuitBreakerRegistry, CircuitBreakerError
from .error_formatter import (
    ErrorContext,
    AzureError,
    format_error_xml,
    format_error_json,
)
from .tracing import (
    create_trace_context,
    set_trace_context,
    get_trace_context,
    Tracer,
)
from .metrics import get_metrics_collector

logger = logging.getLogger(__name__)


class GatewayMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for gateway functionality."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        hostname_mapper: Optional[HostnameMapper] = None,
        rate_limiter: Optional[RateLimiter] = None,
        circuit_breaker_registry: Optional[CircuitBreakerRegistry] = None,
        enable_tracing: bool = True,
        enable_metrics: bool = True,
    ):
        """Initialize gateway middleware.

        Args:
            app: ASGI application
            hostname_mapper: Optional hostname mapper
            rate_limiter: Optional rate limiter
            circuit_breaker_registry: Optional circuit breaker registry
            enable_tracing: Enable distributed tracing
            enable_metrics: Enable metrics collection
        """
        super().__init__(app)
        self.hostname_mapper = hostname_mapper or HostnameMapper()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.circuit_breaker_registry = (
            circuit_breaker_registry or CircuitBreakerRegistry()
        )
        self.enable_tracing = enable_tracing
        self.enable_metrics = enable_metrics
        self.tracer = Tracer(service_name="gateway") if enable_tracing else None
        self.metrics_collector = (
            get_metrics_collector() if enable_metrics else None
        )

        # Configure default rate limiting rules
        self._configure_default_rate_limits()

        # Configure default circuit breakers
        self._configure_default_circuit_breakers()

    def _configure_default_rate_limits(self) -> None:
        """Configure default rate limiting rules."""
        # Blob storage: 20,000 requests/sec per account
        self.rate_limiter.add_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=20000,
                burst_size=5000,
                scope=RateLimitScope.PER_ACCOUNT,
            ),
        )

        # Table storage: 20,000 requests/sec per account
        self.rate_limiter.add_service_rule(
            "table",
            RateLimitRule(
                requests_per_second=20000,
                burst_size=5000,
                scope=RateLimitScope.PER_ACCOUNT,
            ),
        )

        # Queue storage: 20,000 requests/sec per account
        self.rate_limiter.add_service_rule(
            "queue",
            RateLimitRule(
                requests_per_second=20000,
                burst_size=5000,
                scope=RateLimitScope.PER_ACCOUNT,
            ),
        )

    def _configure_default_circuit_breakers(self) -> None:
        """Configure default circuit breakers."""
        # Create circuit breakers for each service
        for service in ["blob", "table", "queue", "cosmosdb"]:
            self.circuit_breaker_registry.get_or_create(service)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request through gateway middleware.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        start_time = time.time()
        trace_context = None
        span = None

        try:
            # Initialize tracing
            if self.enable_tracing:
                trace_context = create_trace_context(
                    headers=dict(request.headers),
                    operation_name=f"{request.method} {request.url.path}",
                )
                set_trace_context(trace_context)

                # Start span
                span = self.tracer.start_span(
                    operation_name=f"{request.method} {request.url.path}",
                    context=trace_context,
                    attributes={
                        "http.method": request.method,
                        "http.url": str(request.url),
                        "http.host": request.url.hostname,
                        "http.path": request.url.path,
                    },
                )

                # Add tracing headers to request
                for key, value in trace_context.to_headers().items():
                    request.headers.__dict__["_list"].append(
                        (key.lower().encode(), value.encode())
                    )

            # Increment active requests gauge
            if self.enable_metrics:
                active_gauge = self.metrics_collector.create_gauge(
                    "gateway_active_requests",
                    "Active requests",
                    labels={"service": "gateway"},
                )
                active_gauge.inc()

            # Map hostname to service
            service_mapping = self._get_service_mapping(request)

            if span:
                span.set_attribute("service.name", service_mapping.service_name)
                span.set_attribute("service.account", service_mapping.account_or_namespace or "default")

            # Check rate limiting
            await self._check_rate_limit(request, service_mapping)

            if span:
                span.add_event("rate_limit_checked")

            # Execute request through circuit breaker
            response = await self._execute_with_circuit_breaker(
                request, call_next, service_mapping
            )

            if span:
                span.set_attribute("http.status_code", response.status_code)
                span.add_event("request_completed")

            # Record metrics
            if self.enable_metrics:
                duration = time.time() - start_time
                self.metrics_collector.record_request(
                    service=service_mapping.service_name,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_seconds=duration,
                )

            # Add tracing headers to response
            if trace_context:
                for key, value in trace_context.to_headers().items():
                    response.headers[key] = value

            # Finish span
            if span:
                status = "ok" if response.status_code < 400 else "error"
                span.finish(status=status)

            return response

        except Exception as e:
            # Handle errors
            logger.error(
                f"Gateway error: {e}",
                extra={
                    "correlation_id": (
                        trace_context.correlation_id if trace_context else None
                    )
                },
            )

            if span:
                span.add_event("error", {"error.message": str(e)})
                span.finish(status="error", error_message=str(e))

            # Format error response
            error_response = await self._format_error_response(
                request, e, service_mapping if "service_mapping" in locals() else None
            )

            # Record error metrics
            if self.enable_metrics:
                duration = time.time() - start_time
                self.metrics_collector.record_request(
                    service=(
                        service_mapping.service_name
                        if "service_mapping" in locals()
                        else "unknown"
                    ),
                    method=request.method,
                    path=request.url.path,
                    status_code=error_response.status_code,
                    duration_seconds=duration,
                )

            return error_response

        finally:
            # Decrement active requests gauge
            if self.enable_metrics:
                active_gauge = self.metrics_collector.create_gauge(
                    "gateway_active_requests",
                    "Active requests",
                    labels={"service": "gateway"},
                )
                active_gauge.dec()

    def _get_service_mapping(self, request: Request) -> MappingResult:
        """Get service mapping from request.

        Args:
            request: FastAPI request

        Returns:
            MappingResult
        """
        hostname = request.url.hostname or ""
        # Map the full URL to get account/service information
        full_url = str(request.url)
        return self.hostname_mapper.map_url(full_url)

    async def _check_rate_limit(
        self, request: Request, service_mapping: MappingResult
    ) -> None:
        """Check rate limiting.

        Args:
            request: FastAPI request
            service_mapping: Service mapping

        Raises:
            Exception: If rate limit exceeded
        """
        client_id = request.client.host if request.client else "unknown"

        allowed = await self.rate_limiter.check_rate_limit(
            service=service_mapping.service_name,
            account_name=service_mapping.account_or_namespace or "default",
            client_id=client_id,
        )

        if not allowed:
            # Record rate limit violation
            if self.enable_metrics:
                self.metrics_collector.record_rate_limit_exceeded(
                    service=service_mapping.service_name,
                    client_id=client_id,
                )

            # Raise rate limit error
            raise Exception("Rate limit exceeded")

    async def _execute_with_circuit_breaker(
        self,
        request: Request,
        call_next: Callable,
        service_mapping: MappingResult,
    ) -> Response:
        """Execute request through circuit breaker.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            service_mapping: Service mapping

        Returns:
            Response
        """
        circuit_breaker = self.circuit_breaker_registry.get_or_create(
            service_mapping.service_name
        )

        async def execute_request() -> Response:
            return await call_next(request)

        try:
            response = await circuit_breaker.call(execute_request)

            # Record circuit breaker state
            if self.enable_metrics:
                self.metrics_collector.record_circuit_breaker_state(
                    service=service_mapping.service_name,
                    state=circuit_breaker.state.value,
                )

            return response

        except CircuitBreakerError as e:
            logger.warning(
                f"Circuit breaker open for {service_mapping.service_name}: {e}"
            )

            # Record circuit breaker state
            if self.enable_metrics:
                self.metrics_collector.record_circuit_breaker_state(
                    service=service_mapping.service_name,
                    state=circuit_breaker.state.value,
                )

            # Return service unavailable error
            raise Exception(f"Service {service_mapping.service_name} is unavailable")

    async def _format_error_response(
        self,
        request: Request,
        error: Exception,
        service_mapping: Optional[MappingResult] = None,
    ) -> Response:
        """Format error response.

        Args:
            request: FastAPI request
            error: Exception
            service_mapping: Optional service mapping

        Returns:
            Error response
        """
        # Determine error code and status
        error_message = str(error)
        status_code = 500

        if "Rate limit exceeded" in error_message:
            error_code = "TooManyRequests"
            status_code = 429
        elif "unavailable" in error_message.lower():
            error_code = "ServiceUnavailable"
            status_code = 503
        else:
            error_code = "InternalError"
            status_code = 500

        # Create error context
        context = ErrorContext(
            service=(
                service_mapping.service_name if service_mapping else "gateway"
            ),
            operation=f"{request.method} {request.url.path}",
            resource_type="gateway",
            timestamp=datetime.now(timezone.utc),
            correlation_id=(
                get_trace_context().correlation_id if get_trace_context() else None
            ),
        )

        # Create Azure error
        azure_error = AzureError(
            code=error_code,
            message=error_message,
            status=status_code,
        )

        # Format error response
        content_type = "application/json"
        if service_mapping and service_mapping.service_name in ["blob", "queue", "file"]:
            content_type = "application/xml"

        # Format error body
        if content_type == "application/xml":
            error_body = format_error_xml(context)
        else:
            error_body = format_error_json(context)

        return Response(
            content=error_body,
            status_code=status_code,
            media_type=content_type,
            headers={
                "x-ms-error-code": error_code,
                "x-ms-request-id": context.correlation_id or "",
            },
        )
