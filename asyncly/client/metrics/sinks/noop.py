from asyncly.client.metrics.sinks.base import BaseMetricsSink


class NoopSink(BaseMetricsSink):
    """The default sink: records nothing and adds no overhead."""

    def observe_request(
        self,
        *,
        client: str,
        method: str,
        route: str,
        operation: str = "",
        status: int | str,
        outcome: str = "response",
        duration_seconds: float,
        error_type: str | None = None,
    ) -> None:
        return
