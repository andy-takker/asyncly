from typing import Protocol


class MetricsSink(Protocol):
    """Protocol for metrics backends used by `InstrumentableHttpClient`.

    Implement `observe_request` to record requests in any backend.
    """

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
        """Record a single completed request.

        Args:
            client: The client name (`client_name`).
            method: HTTP method.
            route: Normalized, low-cardinality route label.
            status: Response status code, or a string marker on error.
            duration_seconds: Total time including response handling.
            error_type: Exception class name if the request failed, else None.
        """
        ...
