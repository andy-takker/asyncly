class NoopSink:
    """Синк по умолчанию: ничего не делает."""

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
        return
