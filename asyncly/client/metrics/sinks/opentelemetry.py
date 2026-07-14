from opentelemetry.metrics import Meter

from asyncly.client.metrics.sinks.base import BaseMetricsSink
from asyncly.client.metrics.taxonomy import (
    ERROR_OUTCOME,
    NONE,
    RESPONSE,
    RESPONSE_OUTCOME,
)


class OpenTelemetrySink(BaseMetricsSink):
    """Metrics sink backed by OpenTelemetry (needs the ``opentelemetry`` extra).

    Records request counts, durations, errors, and in-flight requests through the
    given `Meter`. Metric names match the Prometheus sink defaults
    (``http_client_*``). ``status`` is kept off the duration histogram; the
    counter carries it.

    Args:
        meter: An OpenTelemetry `Meter` to create instruments from.
    """

    def __init__(self, meter: Meter) -> None:
        self._req_counter = meter.create_counter(
            name="http_client_requests_total",
            unit="1",
            description="Total HTTP client requests",
        )
        self._req_hist = meter.create_histogram(
            name="http_client_request_seconds",
            unit="s",
            description="HTTP client request duration including handler",
        )
        self._err_counter = meter.create_counter(
            name="http_client_errors_total",
            unit="1",
            description="Total HTTP client errors",
        )
        self._in_flight = meter.create_up_down_counter(
            name="http_client_in_flight",
            unit="1",
            description="In-progress HTTP client requests",
        )
        self._phase_hist = meter.create_histogram(
            name="http_client_phase_duration_seconds",
            unit="s",
            description="HTTP client network phase duration",
        )

    def observe_phase(
        self, *, client: str, operation: str, phase: str, seconds: float
    ) -> None:
        self._phase_hist.record(
            seconds,
            attributes={"client": client, "operation": operation, "phase": phase},
        )

    def on_request_start(
        self, *, client: str, method: str, route: str, operation: str
    ) -> None:
        self._in_flight.add(
            1,
            attributes={
                "client": client,
                "method": method,
                "route": route,
                "operation": operation,
            },
        )

    def on_request_end(
        self, *, client: str, method: str, route: str, operation: str
    ) -> None:
        self._in_flight.add(
            -1,
            attributes={
                "client": client,
                "method": method,
                "route": route,
                "operation": operation,
            },
        )

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
        base = {
            "client": client,
            "method": method,
            "route": route,
            "operation": operation,
        }
        hist_outcome = RESPONSE_OUTCOME if outcome == RESPONSE else ERROR_OUTCOME
        self._req_counter.add(
            1, attributes={**base, "status": str(status), "outcome": outcome}
        )
        self._req_hist.record(
            duration_seconds, attributes={**base, "outcome": hist_outcome}
        )
        if error_type and error_type != NONE:
            self._err_counter.add(1, attributes={**base, "error_type": error_type})
