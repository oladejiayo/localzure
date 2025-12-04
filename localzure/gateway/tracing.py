"""Request tracing and correlation for LocalZure Gateway.

This module provides distributed tracing with correlation IDs for
tracking requests across services and components.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any
import logging
import contextvars

logger = logging.getLogger(__name__)

# Context variable for current trace context
_trace_context = contextvars.ContextVar("trace_context", default=None)


@dataclass
class TraceContext:
    """Trace context for request tracking."""

    correlation_id: str
    request_id: str
    parent_id: Optional[str] = None
    service_name: str = "gateway"
    operation_name: Optional[str] = None
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    baggage: Dict[str, str] = field(default_factory=dict)

    def to_headers(self) -> Dict[str, str]:
        """Convert trace context to HTTP headers.

        Returns:
            Dictionary of tracing headers
        """
        headers = {
            "X-Correlation-ID": self.correlation_id,
            "X-Request-ID": self.request_id,
            "X-Service-Name": self.service_name,
        }

        if self.parent_id:
            headers["X-Parent-ID"] = self.parent_id

        if self.operation_name:
            headers["X-Operation-Name"] = self.operation_name

        # Add baggage items
        for key, value in self.baggage.items():
            headers[f"X-Baggage-{key}"] = value

        return headers

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> "TraceContext":
        """Create trace context from HTTP headers.

        Args:
            headers: HTTP headers dictionary

        Returns:
            TraceContext object
        """
        # Normalize header keys to lowercase for case-insensitive lookup
        headers_lower = {k.lower(): v for k, v in headers.items()}

        correlation_id = headers_lower.get("x-correlation-id") or str(uuid.uuid4())
        request_id = headers_lower.get("x-request-id") or str(uuid.uuid4())
        parent_id = headers_lower.get("x-parent-id")
        service_name = headers_lower.get("x-service-name", "gateway")
        operation_name = headers_lower.get("x-operation-name")

        # Extract baggage items
        baggage = {}
        for key, value in headers_lower.items():
            if key.startswith("x-baggage-"):
                baggage_key = key[10:]  # Remove "x-baggage-" prefix
                baggage[baggage_key] = value

        return cls(
            correlation_id=correlation_id,
            request_id=request_id,
            parent_id=parent_id,
            service_name=service_name,
            operation_name=operation_name,
            baggage=baggage,
        )

    def create_child(
        self, operation_name: str, service_name: Optional[str] = None
    ) -> "TraceContext":
        """Create child trace context for sub-operation.

        Args:
            operation_name: Name of the child operation
            service_name: Optional service name (defaults to parent's)

        Returns:
            Child TraceContext
        """
        return TraceContext(
            correlation_id=self.correlation_id,
            request_id=str(uuid.uuid4()),
            parent_id=self.request_id,
            service_name=service_name or self.service_name,
            operation_name=operation_name,
            baggage=self.baggage.copy(),
        )


@dataclass
class SpanEvent:
    """Event within a span."""

    name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """Trace span for operation timing."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "ok"  # ok, error, timeout
    error_message: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        """Get span duration in milliseconds.

        Returns:
            Duration in milliseconds, or None if not ended
        """
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add event to span.

        Args:
            name: Event name
            attributes: Optional event attributes
        """
        event = SpanEvent(name=name, attributes=attributes or {})
        self.events.append(event)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set span attribute.

        Args:
            key: Attribute key
            value: Attribute value
        """
        self.attributes[key] = value

    def finish(self, status: str = "ok", error_message: Optional[str] = None) -> None:
        """Finish the span.

        Args:
            status: Final status (ok, error, timeout)
            error_message: Optional error message
        """
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        if error_message:
            self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary.

        Returns:
            Span as dictionary
        """
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "service_name": self.service_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_message": self.error_message,
            "attributes": self.attributes,
            "events": [
                {
                    "name": event.name,
                    "timestamp": event.timestamp.isoformat(),
                    "attributes": event.attributes,
                }
                for event in self.events
            ],
        }


class Tracer:
    """Request tracer for distributed tracing."""

    def __init__(self, service_name: str = "gateway"):
        """Initialize tracer.

        Args:
            service_name: Name of the service
        """
        self.service_name = service_name
        self._spans: List[Span] = []

    def start_span(
        self,
        operation_name: str,
        *,
        context: Optional[TraceContext] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span.

        Args:
            operation_name: Name of the operation
            context: Optional trace context
            attributes: Optional initial attributes

        Returns:
            Started span
        """
        if context is None:
            context = get_trace_context() or TraceContext(
                correlation_id=str(uuid.uuid4()),
                request_id=str(uuid.uuid4()),
                service_name=self.service_name,
            )

        span = Span(
            trace_id=context.correlation_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=context.parent_id,
            operation_name=operation_name,
            service_name=context.service_name,
            start_time=datetime.now(timezone.utc),
            attributes=attributes or {},
        )

        self._spans.append(span)
        return span

    def get_spans(
        self, *, trace_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[Span]:
        """Get spans matching criteria.

        Args:
            trace_id: Filter by trace ID
            status: Filter by status

        Returns:
            List of matching spans
        """
        spans = self._spans

        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]

        if status:
            spans = [s for s in spans if s.status == status]

        return spans

    def clear_spans(self) -> None:
        """Clear all stored spans."""
        self._spans.clear()


def create_trace_context(
    *,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    operation_name: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> TraceContext:
    """Create trace context.

    Args:
        correlation_id: Optional correlation ID (generated if not provided)
        request_id: Optional request ID (generated if not provided)
        operation_name: Optional operation name
        headers: Optional HTTP headers to extract context from

    Returns:
        TraceContext object
    """
    if headers:
        context = TraceContext.from_headers(headers)
        if operation_name:
            context.operation_name = operation_name
        return context

    return TraceContext(
        correlation_id=correlation_id or str(uuid.uuid4()),
        request_id=request_id or str(uuid.uuid4()),
        operation_name=operation_name,
    )


def set_trace_context(context: TraceContext) -> None:
    """Set trace context for current execution.

    Args:
        context: Trace context to set
    """
    _trace_context.set(context)


def get_trace_context() -> Optional[TraceContext]:
    """Get trace context for current execution.

    Returns:
        Current trace context or None
    """
    return _trace_context.get()


def add_baggage(key: str, value: str) -> None:
    """Add baggage item to current trace context.

    Args:
        key: Baggage key
        value: Baggage value
    """
    context = get_trace_context()
    if context:
        context.baggage[key] = value


def get_baggage(key: str) -> Optional[str]:
    """Get baggage item from current trace context.

    Args:
        key: Baggage key

    Returns:
        Baggage value or None
    """
    context = get_trace_context()
    if context:
        return context.baggage.get(key)
    return None


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from current trace context.

    Returns:
        Correlation ID or None
    """
    context = get_trace_context()
    return context.correlation_id if context else None


def get_request_id() -> Optional[str]:
    """Get request ID from current trace context.

    Returns:
        Request ID or None
    """
    context = get_trace_context()
    return context.request_id if context else None
