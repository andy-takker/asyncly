from typing import Protocol, runtime_checkable


@runtime_checkable
class MetricsSink(Protocol):
    """Protocol for metrics backends used by `InstrumentableHttpClient`.

    Implement `observe_request` to record completed requests in any backend.

    `on_request_start` / `on_request_end` are **optional**: they bracket the
    in-flight window (increment on start, decrement on end). The client detects
    their presence once, when the sink is enabled, and only calls them if both
    are defined — so an existing sink that implements only `observe_request`
    keeps working unchanged. New sinks can inherit `BaseMetricsSink` to get no-op
    defaults for the optional hooks.
    """

    def observe_request(
        self,
        *,
        client: str,
        method: str,
        route: str,
        operation: str,
        status: int | str,
        outcome: str,
        duration_seconds: float,
        error_type: str | None = None,
    ) -> None:
        """Record a single completed request.

        Args:
            client: The client name (`client_name`).
            method: HTTP method.
            route: Normalized, low-cardinality route label.
            operation: Logical operation name; falls back to `route`.
            status: Response status code, or a string marker on error.
            outcome: One of ``response``, ``timeout``, ``network_error``,
                ``cancelled``.
            duration_seconds: Total time including response handling.
            error_type: Normalized error taxonomy value on failure, else None.
        """
        ...

    def on_request_start(
        self, *, client: str, method: str, route: str, operation: str
    ) -> None:
        """Signal a request is about to be issued (in-flight increment)."""
        ...

    def on_request_end(
        self, *, client: str, method: str, route: str, operation: str
    ) -> None:
        """Signal a request has finished (in-flight decrement)."""
        ...

    def observe_phase(
        self, *, client: str, operation: str, phase: str, seconds: float
    ) -> None:
        """Record the duration of a network phase (dns, connect, ttfb, ...).

        Fed by the aiohttp `TraceConfig` from
        [`build_trace_config`][asyncly.client.metrics.trace_config.build_trace_config].
        Optional: the client only wires trace context through when the sink
        defines this method.
        """
        ...


class BaseMetricsSink:
    """Convenience base with no-op optional hooks for sinks authored here.

    Note:
        This is a convenience for *new* sinks. It is **not** the
        backward-compatibility mechanism: because `MetricsSink` is a structural
        `Protocol`, an external sink that implements only `observe_request`
        inherits nothing from this class. Compatibility is guaranteed at the
        call site, where `InstrumentableHttpClient` feature-detects the optional
        hooks before calling them.
    """

    def on_request_start(
        self, *, client: str, method: str, route: str, operation: str
    ) -> None:
        return

    def on_request_end(
        self, *, client: str, method: str, route: str, operation: str
    ) -> None:
        return

    def observe_phase(
        self, *, client: str, operation: str, phase: str, seconds: float
    ) -> None:
        return
