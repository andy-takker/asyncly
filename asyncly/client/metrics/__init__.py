"""Client metrics: instrumentable client, sinks, taxonomy, and tracing.

Always-safe symbols (no optional dependencies) are exported eagerly. The
backend-specific sinks pull in optional extras (``prometheus_client``,
``opentelemetry``), so they are exposed lazily via ``__getattr__`` — importing
this package never fails just because an extra is missing.
"""

from typing import Any

from asyncly.client.metrics.instrumentable_client import InstrumentableHttpClient
from asyncly.client.metrics.route_resolver import default_route_resolver
from asyncly.client.metrics.sinks.base import BaseMetricsSink, MetricsSink
from asyncly.client.metrics.sinks.noop import NoopSink
from asyncly.client.metrics.trace_config import build_trace_config

__all__ = (
    "InstrumentableHttpClient",
    "MetricsSink",
    "BaseMetricsSink",
    "NoopSink",
    "default_route_resolver",
    "build_trace_config",
    # Lazy (require optional extras):
    "PrometheusSink",
    "PrometheusPoolCollector",
    "OpenTelemetrySink",
)


def __getattr__(name: str) -> Any:
    if name in ("PrometheusSink", "PrometheusPoolCollector"):
        from asyncly.client.metrics.sinks import prometheus

        return getattr(prometheus, name)
    if name == "OpenTelemetrySink":
        from asyncly.client.metrics.sinks.opentelemetry import OpenTelemetrySink

        return OpenTelemetrySink
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
