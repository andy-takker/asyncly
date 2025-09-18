from opentelemetry.metrics import Meter


class OpenTelemetrySink:
    def __init__(self, meter: Meter) -> None:
        # Counter: количество
        self._req_counter = meter.create_counter(
            name="http_client_requests_total",
            unit="1",
            description="Total HTTP client requests",
        )
        # Histogram: длительность
        self._req_hist = meter.create_histogram(
            name="http_client_request_seconds",
            unit="s",
            description="HTTP client request duration including handler",
        )
        # Counter: ошибки
        self._err_counter = meter.create_counter(
            name="http_client_errors_total",
            unit="1",
            description="Total HTTP client errors",
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
        attrs = {
            "client": client,
            "method": method,
            "route": route,
            "status": str(status),
        }
        self._req_counter.add(1, attributes=attrs)
        self._req_hist.record(duration_seconds, attributes=attrs)
        if error_type:
            self._err_counter.add(
                1,
                attributes={
                    "client": client,
                    "method": method,
                    "route": route,
                    "error_type": error_type,
                },
            )
