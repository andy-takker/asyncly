from collections.abc import Iterable

from prometheus_client import Counter, Histogram
from prometheus_client.registry import REGISTRY, CollectorRegistry


class PrometheusSink:
    def __init__(
        self,
        namespace: str = "asyncly",
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
        registry: CollectorRegistry = REGISTRY,
    ) -> None:
        metric_prefix = f"{namespace}_{subsystem}"
        self._latency = Histogram(
            f"{metric_prefix}_request_seconds",
            "HTTP client request duration including handler",
            ("client", "method", "route", "status"),
            buckets=tuple(buckets),
            registry=registry,
        )
        self._total = Counter(
            f"{metric_prefix}_requests_total",
            "Total HTTP client requests",
            ("client", "method", "route", "status"),
            registry=registry,
        )
        self._errors = Counter(
            f"{metric_prefix}_errors_total",
            "Total HTTP client errors",
            ("client", "method", "route", "error_type"),
            registry=registry,
        )

    def observe_request(
        self,
        *,
        client: str,
        method: str,
        route: str,
        status: int | str,
        duration_seconds: float,
        error_type: str | None = None,
    ) -> None:
        status_label = str(status)
        self._total.labels(client, method, route, status_label).inc()
        self._latency.labels(client, method, route, status_label).observe(
            duration_seconds
        )
        if error_type:
            self._errors.labels(client, method, route, error_type).inc()
