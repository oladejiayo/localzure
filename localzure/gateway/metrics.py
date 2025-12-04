"""Metrics collection for LocalZure Gateway.

This module provides Prometheus-compatible metrics collection
for monitoring gateway performance and health.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
import threading
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric type enumeration."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricLabels:
    """Labels for metrics."""

    service: str
    operation: Optional[str] = None
    status_code: Optional[int] = None
    error_type: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        """Convert labels to dictionary.

        Returns:
            Dictionary of non-None labels
        """
        return {
            k: str(v)
            for k, v in {
                "service": self.service,
                "operation": self.operation,
                "status_code": self.status_code,
                "error_type": self.error_type,
                "method": self.method,
                "path": self.path,
            }.items()
            if v is not None
        }


@dataclass
class CounterMetric:
    """Counter metric (monotonically increasing)."""

    name: str
    description: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def inc(self, amount: float = 1.0) -> None:
        """Increment counter.

        Args:
            amount: Amount to increment by
        """
        self.value += amount


@dataclass
class GaugeMetric:
    """Gauge metric (can go up or down)."""

    name: str
    description: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float) -> None:
        """Set gauge value.

        Args:
            value: New value
        """
        self.value = value

    def inc(self, amount: float = 1.0) -> None:
        """Increment gauge.

        Args:
            amount: Amount to increment by
        """
        self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        """Decrement gauge.

        Args:
            amount: Amount to decrement by
        """
        self.value -= amount


@dataclass
class HistogramBucket:
    """Histogram bucket."""

    upper_bound: float
    count: int = 0


@dataclass
class HistogramMetric:
    """Histogram metric for distributions."""

    name: str
    description: str
    buckets: List[HistogramBucket] = field(default_factory=list)
    sum: float = 0.0
    count: int = 0
    labels: Dict[str, str] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        """Observe a value.

        Args:
            value: Value to observe
        """
        self.sum += value
        self.count += 1

        for bucket in self.buckets:
            if value <= bucket.upper_bound:
                bucket.count += 1

    @property
    def average(self) -> float:
        """Get average of observed values.

        Returns:
            Average value
        """
        return self.sum / self.count if self.count > 0 else 0.0


@dataclass
class SummaryMetric:
    """Summary metric with quantiles."""

    name: str
    description: str
    sum: float = 0.0
    count: int = 0
    quantiles: Dict[float, float] = field(default_factory=dict)  # quantile -> value
    labels: Dict[str, str] = field(default_factory=dict)
    _values: List[float] = field(default_factory=list)

    def observe(self, value: float) -> None:
        """Observe a value.

        Args:
            value: Value to observe
        """
        self.sum += value
        self.count += 1
        self._values.append(value)

        # Update quantiles (simplified - in production use a proper algorithm)
        if len(self._values) > 0:
            sorted_values = sorted(self._values)
            for q in [0.5, 0.9, 0.95, 0.99]:
                idx = int(len(sorted_values) * q)
                if idx < len(sorted_values):
                    self.quantiles[q] = sorted_values[idx]

    @property
    def average(self) -> float:
        """Get average of observed values.

        Returns:
            Average value
        """
        return self.sum / self.count if self.count > 0 else 0.0


class MetricsCollector:
    """Metrics collector for gateway monitoring."""

    def __init__(self):
        """Initialize metrics collector."""
        self._lock = threading.RLock()
        self._counters: Dict[str, CounterMetric] = {}
        self._gauges: Dict[str, GaugeMetric] = {}
        self._histograms: Dict[str, HistogramMetric] = {}
        self._summaries: Dict[str, SummaryMetric] = {}

        # Initialize default metrics
        self._init_default_metrics()

    def _init_default_metrics(self) -> None:
        """Initialize default gateway metrics."""
        # Request counters
        self.create_counter(
            "gateway_requests_total",
            "Total number of requests",
            labels={"service": "gateway"},
        )

        self.create_counter(
            "gateway_errors_total",
            "Total number of errors",
            labels={"service": "gateway"},
        )

        # Request duration histogram
        self.create_histogram(
            "gateway_request_duration_seconds",
            "Request duration in seconds",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            labels={"service": "gateway"},
        )

        # Active requests gauge
        self.create_gauge(
            "gateway_active_requests",
            "Number of requests currently being processed",
            labels={"service": "gateway"},
        )

        # Rate limiting metrics
        self.create_counter(
            "gateway_rate_limit_exceeded_total",
            "Total number of rate limit violations",
            labels={"service": "gateway"},
        )

        # Circuit breaker metrics
        self.create_gauge(
            "gateway_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            labels={"service": "gateway"},
        )

        self.create_counter(
            "gateway_circuit_breaker_transitions_total",
            "Total circuit breaker state transitions",
            labels={"service": "gateway"},
        )

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create unique key for metric.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Unique metric key
        """
        if not labels:
            return name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def create_counter(
        self,
        name: str,
        description: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> CounterMetric:
        """Create or get counter metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional labels

        Returns:
            Counter metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self._counters:
                self._counters[key] = CounterMetric(
                    name=name,
                    description=description,
                    labels=labels or {},
                )
            return self._counters[key]

    def create_gauge(
        self,
        name: str,
        description: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> GaugeMetric:
        """Create or get gauge metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional labels

        Returns:
            Gauge metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self._gauges:
                self._gauges[key] = GaugeMetric(
                    name=name,
                    description=description,
                    labels=labels or {},
                )
            return self._gauges[key]

    def create_histogram(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> HistogramMetric:
        """Create or get histogram metric.

        Args:
            name: Metric name
            description: Metric description
            buckets: Bucket upper bounds
            labels: Optional labels

        Returns:
            Histogram metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self._histograms:
                default_buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
                bucket_bounds = buckets or default_buckets

                histogram = HistogramMetric(
                    name=name,
                    description=description,
                    buckets=[
                        HistogramBucket(upper_bound=b) for b in sorted(bucket_bounds)
                    ],
                    labels=labels or {},
                )
                self._histograms[key] = histogram
            return self._histograms[key]

    def create_summary(
        self,
        name: str,
        description: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> SummaryMetric:
        """Create or get summary metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional labels

        Returns:
            Summary metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self._summaries:
                self._summaries[key] = SummaryMetric(
                    name=name,
                    description=description,
                    labels=labels or {},
                )
            return self._summaries[key]

    def record_request(
        self,
        service: str,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record request metrics.

        Args:
            service: Service name
            method: HTTP method
            path: Request path
            status_code: HTTP status code
            duration_seconds: Request duration in seconds
        """
        labels = {
            "service": service,
            "method": method,
            "path": path,
            "status_code": str(status_code),
        }

        # Increment request counter
        counter = self.create_counter(
            "gateway_requests_total",
            "Total requests",
            labels=labels,
        )
        counter.inc()

        # Record duration
        histogram = self.create_histogram(
            "gateway_request_duration_seconds",
            "Request duration",
            labels=labels,
        )
        histogram.observe(duration_seconds)

        # Increment error counter if needed
        if status_code >= 400:
            error_counter = self.create_counter(
                "gateway_errors_total",
                "Total errors",
                labels=labels,
            )
            error_counter.inc()

    def record_rate_limit_exceeded(
        self,
        service: str,
        client_id: Optional[str] = None,
    ) -> None:
        """Record rate limit violation.

        Args:
            service: Service name
            client_id: Optional client ID
        """
        labels = {"service": service}
        if client_id:
            labels["client_id"] = client_id

        counter = self.create_counter(
            "gateway_rate_limit_exceeded_total",
            "Rate limit violations",
            labels=labels,
        )
        counter.inc()

    def record_circuit_breaker_state(
        self,
        service: str,
        state: str,
    ) -> None:
        """Record circuit breaker state.

        Args:
            service: Service name
            state: Circuit state (closed, open, half_open)
        """
        state_map = {"closed": 0, "open": 1, "half_open": 2}

        gauge = self.create_gauge(
            "gateway_circuit_breaker_state",
            "Circuit breaker state",
            labels={"service": service},
        )
        gauge.set(state_map.get(state.lower(), 0))

    def record_circuit_breaker_transition(
        self,
        service: str,
        from_state: str,
        to_state: str,
    ) -> None:
        """Record circuit breaker state transition.

        Args:
            service: Service name
            from_state: Previous state
            to_state: New state
        """
        counter = self.create_counter(
            "gateway_circuit_breaker_transitions_total",
            "Circuit breaker transitions",
            labels={
                "service": service,
                "from_state": from_state,
                "to_state": to_state,
            },
        )
        counter.inc()

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as dictionary.

        Returns:
            Dictionary of all metrics
        """
        with self._lock:
            metrics = {
                "counters": {
                    key: {
                        "name": m.name,
                        "description": m.description,
                        "value": m.value,
                        "labels": m.labels,
                    }
                    for key, m in self._counters.items()
                },
                "gauges": {
                    key: {
                        "name": m.name,
                        "description": m.description,
                        "value": m.value,
                        "labels": m.labels,
                    }
                    for key, m in self._gauges.items()
                },
                "histograms": {
                    key: {
                        "name": m.name,
                        "description": m.description,
                        "sum": m.sum,
                        "count": m.count,
                        "average": m.average,
                        "buckets": [
                            {"upper_bound": b.upper_bound, "count": b.count}
                            for b in m.buckets
                        ],
                        "labels": m.labels,
                    }
                    for key, m in self._histograms.items()
                },
                "summaries": {
                    key: {
                        "name": m.name,
                        "description": m.description,
                        "sum": m.sum,
                        "count": m.count,
                        "average": m.average,
                        "quantiles": m.quantiles,
                        "labels": m.labels,
                    }
                    for key, m in self._summaries.items()
                },
            }
            return metrics

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics
        """
        lines = []

        with self._lock:
            # Counters
            for key, metric in self._counters.items():
                lines.append(f"# HELP {metric.name} {metric.description}")
                lines.append(f"# TYPE {metric.name} counter")
                label_str = (
                    ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                    if metric.labels
                    else ""
                )
                metric_line = (
                    f"{metric.name}{{{label_str}}} {metric.value}"
                    if label_str
                    else f"{metric.name} {metric.value}"
                )
                lines.append(metric_line)

            # Gauges
            for key, metric in self._gauges.items():
                lines.append(f"# HELP {metric.name} {metric.description}")
                lines.append(f"# TYPE {metric.name} gauge")
                label_str = (
                    ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                    if metric.labels
                    else ""
                )
                metric_line = (
                    f"{metric.name}{{{label_str}}} {metric.value}"
                    if label_str
                    else f"{metric.name} {metric.value}"
                )
                lines.append(metric_line)

            # Histograms
            for key, metric in self._histograms.items():
                lines.append(f"# HELP {metric.name} {metric.description}")
                lines.append(f"# TYPE {metric.name} histogram")

                label_str = (
                    ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                    if metric.labels
                    else ""
                )

                for bucket in metric.buckets:
                    bucket_labels = (
                        f'{label_str},le="{bucket.upper_bound}"'
                        if label_str
                        else f'le="{bucket.upper_bound}"'
                    )
                    lines.append(f"{metric.name}_bucket{{{bucket_labels}}} {bucket.count}")

                inf_labels = (
                    f'{label_str},le="+Inf"' if label_str else 'le="+Inf"'
                )
                lines.append(f"{metric.name}_bucket{{{inf_labels}}} {metric.count}")
                lines.append(
                    f"{metric.name}_sum{{{label_str}}} {metric.sum}"
                    if label_str
                    else f"{metric.name}_sum {metric.sum}"
                )
                lines.append(
                    f"{metric.name}_count{{{label_str}}} {metric.count}"
                    if label_str
                    else f"{metric.name}_count {metric.count}"
                )

        return "\n".join(lines) + "\n"


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector.

    Returns:
        MetricsCollector instance
    """
    return _metrics_collector
