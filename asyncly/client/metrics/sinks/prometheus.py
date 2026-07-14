from collections.abc import Iterable, Iterator
from typing import Any

from prometheus_client import Counter, Gauge, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import REGISTRY, Collector, CollectorRegistry

from asyncly.client.metrics.sinks.base import BaseMetricsSink
from asyncly.client.metrics.taxonomy import (
    ERROR_OUTCOME,
    NONE,
    RESPONSE,
    RESPONSE_OUTCOME,
)

# Finer defaults than the request histogram: network phases (dns/connect/ttfb)
# are usually sub-100ms and a coarse bucket set hides regressions in them.
_DEFAULT_PHASE_BUCKETS = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
)


class PrometheusSink(BaseMetricsSink):
    """Metrics sink that records to Prometheus (needs the ``prometheus`` extra).

    Exposes:

    - ``{prefix}_request_seconds`` — duration histogram, labeled by client,
      method, route, operation, and a compact ``outcome`` (``response`` or
      ``error``). ``status`` is intentionally kept off the histogram: each extra
      label multiplies the number of time series by the bucket count.
    - ``{prefix}_requests_total`` — request counter, labeled by client, method,
      route, operation, status, and the full ``outcome``.
    - ``{prefix}_errors_total`` — error counter, labeled by client, method,
      route, operation, and normalized ``error_type``.
    - ``{prefix}_in_flight`` — gauge of in-progress requests.

    Args:
        namespace: Prometheus metric namespace prefix. Defaults to ``http`` so
            the metric names match the ``http_client_*`` convention shared with
            the OpenTelemetry sink. Set ``namespace="asyncly"`` to restore the
            historical ``asyncly_client_*`` names.
        subsystem: Prometheus metric subsystem prefix.
        buckets: Histogram bucket boundaries in seconds.
        registry: Collector registry to register the metrics on.
    """

    def __init__(
        self,
        namespace: str = "http",
        subsystem: str = "client",
        buckets: Iterable[float] = (
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
        ),
        phase_buckets: Iterable[float] = _DEFAULT_PHASE_BUCKETS,
        registry: CollectorRegistry = REGISTRY,
    ) -> None:
        metric_prefix = f"{namespace}_{subsystem}"
        self._latency = Histogram(
            f"{metric_prefix}_request_seconds",
            "HTTP client request duration including handler",
            ("client", "method", "route", "operation", "outcome"),
            buckets=tuple(buckets),
            registry=registry,
        )
        self._total = Counter(
            f"{metric_prefix}_requests_total",
            "Total HTTP client requests",
            ("client", "method", "route", "operation", "status", "outcome"),
            registry=registry,
        )
        self._errors = Counter(
            f"{metric_prefix}_errors_total",
            "Total HTTP client errors",
            ("client", "method", "route", "operation", "error_type"),
            registry=registry,
        )
        self._in_flight = Gauge(
            f"{metric_prefix}_in_flight",
            "In-progress HTTP client requests",
            ("client", "method", "route", "operation"),
            registry=registry,
            multiprocess_mode="livesum",
        )
        self._phase = Histogram(
            f"{metric_prefix}_phase_duration_seconds",
            "HTTP client network phase duration",
            ("client", "operation", "phase"),
            buckets=tuple(phase_buckets),
            registry=registry,
        )

    def observe_phase(
        self, *, client: str, operation: str, phase: str, seconds: float
    ) -> None:
        self._phase.labels(client, operation, phase).observe(seconds)

    def on_request_start(
        self, *, client: str, method: str, route: str, operation: str
    ) -> None:
        self._in_flight.labels(client, method, route, operation).inc()

    def on_request_end(
        self, *, client: str, method: str, route: str, operation: str
    ) -> None:
        self._in_flight.labels(client, method, route, operation).dec()

    def observe_request(
        self,
        *,
        client: str,
        method: str,
        route: str,
        operation: str = "",
        status: int | str,
        outcome: str = RESPONSE,
        duration_seconds: float,
        error_type: str | None = None,
    ) -> None:
        status_label = str(status)
        hist_outcome = RESPONSE_OUTCOME if outcome == RESPONSE else ERROR_OUTCOME
        self._total.labels(
            client, method, route, operation, status_label, outcome
        ).inc()
        self._latency.labels(client, method, route, operation, hist_outcome).observe(
            duration_seconds
        )
        if error_type and error_type != NONE:
            self._errors.labels(client, method, route, operation, error_type).inc()


class PrometheusPoolCollector(Collector):
    """Exposes aiohttp `TCPConnector` pool stats as Prometheus gauges.

    Emits ``{prefix}_pool_connections{upstream, state}`` for ``active`` and
    ``idle`` connections. Bind it to a connector once the session exists::

        collector = PrometheusPoolCollector(upstream="bybit")
        collector.bind(session.connector)

    Warning:
        This reads private aiohttp attributes (``_acquired``, ``_conns``), which
        may change between aiohttp versions. Access is guarded: if the internals
        are absent, the collector degrades to emitting nothing rather than
        raising during a scrape.

    Note:
        Pool stats are **connector-scoped**, not client-scoped: a connector
        shared by several clients cannot attribute connections to one of them.
        The ``upstream`` label names the connector, not a single operation.
    """

    def __init__(
        self,
        *,
        upstream: str,
        namespace: str = "http",
        subsystem: str = "client",
    ) -> None:
        self._upstream = upstream
        self._metric_name = f"{namespace}_{subsystem}_pool_connections"
        self._connector: Any = None

    def bind(self, connector: Any) -> None:
        """Attach the connector whose pool stats should be scraped."""
        self._connector = connector

    def collect(self) -> Iterator[GaugeMetricFamily]:
        family = GaugeMetricFamily(
            self._metric_name,
            "aiohttp connection pool size by state",
            labels=("upstream", "state"),
        )
        active, idle = self._read_counts()
        if active is not None:
            family.add_metric((self._upstream, "active"), active)
        if idle is not None:
            family.add_metric((self._upstream, "idle"), idle)
        yield family

    def _read_counts(self) -> tuple[int | None, int | None]:
        connector = self._connector
        if connector is None:
            return None, None
        active: int | None = None
        idle: int | None = None
        acquired = getattr(connector, "_acquired", None)
        if acquired is not None:
            active = len(acquired)
        conns = getattr(connector, "_conns", None)
        if conns is not None:
            try:
                idle = sum(len(v) for v in conns.values())
            except (TypeError, AttributeError):
                idle = None
        return active, idle
