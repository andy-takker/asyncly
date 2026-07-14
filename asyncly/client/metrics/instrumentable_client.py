import asyncio
from http import HTTPStatus
from time import perf_counter
from types import TracebackType
from typing import Any

from aiohttp import BasicAuth, ClientResponse, ClientSession
from aiohttp.client import DEFAULT_TIMEOUT
from yarl import URL

from asyncly.client.base import BaseHttpClient, MethodType
from asyncly.client.metrics.route_resolver import default_route_resolver
from asyncly.client.metrics.sinks.base import MetricsSink
from asyncly.client.metrics.sinks.noop import NoopSink
from asyncly.client.metrics.taxonomy import classify_exception
from asyncly.client.timeout import TimeoutType
from asyncly.client.typing import ResponseHandler, ResponseHandlersType, RouteResolver


class InstrumentableHttpClient(BaseHttpClient):
    """`BaseHttpClient` that records request metrics through a pluggable sink.

    Behaves exactly like [`BaseHttpClient`][asyncly.BaseHttpClient] until a sink
    is enabled. Each completed request reports its client name, method, resolved
    route, logical operation, status, outcome, duration, and error type to the
    active [`MetricsSink`][asyncly.client.metrics.sinks.base.MetricsSink].
    """

    __slots__ = (
        "_metrics_sink",
        "_resolve_route",
        "_sink_has_lifecycle",
        "_sink_has_phases",
    )

    def __init__(
        self,
        url: URL | str,
        session: ClientSession,
        client_name: str,
        *,
        proxy: URL | str | None = None,
        proxy_auth: BasicAuth | None = None,
    ) -> None:
        super().__init__(
            url=url,
            session=session,
            client_name=client_name,
            proxy=proxy,
            proxy_auth=proxy_auth,
        )
        self._metrics_sink: MetricsSink = NoopSink()
        self._resolve_route: RouteResolver = default_route_resolver
        self._sink_has_lifecycle: bool = False
        self._sink_has_phases: bool = False

    def enable_metrics(
        self, sink: MetricsSink, *, route_resolver: RouteResolver | None = None
    ) -> None:
        """Start emitting metrics to ``sink``.

        Args:
            sink: The metrics sink to report each request to.
            route_resolver: Optional override for how request URLs are
                normalized into low-cardinality route labels.
        """
        self._metrics_sink = sink
        self._sink_has_lifecycle = _detect_lifecycle(sink)
        self._sink_has_phases = hasattr(sink, "observe_phase")
        if route_resolver is not None:
            self._resolve_route = route_resolver

    def disable_metrics(self) -> None:
        """Stop emitting metrics (revert to the no-op sink)."""
        self._metrics_sink = NoopSink()
        self._sink_has_lifecycle = False
        self._sink_has_phases = False
        self._resolve_route = default_route_resolver

    def instrument(  # type: ignore[no-untyped-def]
        self, sink: MetricsSink, *, route_resolver: RouteResolver | None = None
    ):
        """Context manager that enables ``sink`` for the duration of a block.

        Restores the previous sink and route resolver on exit.
        """
        client = self

        class _Ctx:
            def __enter__(self) -> "InstrumentableHttpClient":
                self._prev_sink = client._metrics_sink
                self._prev_resolver = client._resolve_route
                self._prev_has_lifecycle = client._sink_has_lifecycle
                self._prev_has_phases = client._sink_has_phases
                client.enable_metrics(sink, route_resolver=route_resolver)
                return client

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                client._metrics_sink = self._prev_sink
                client._resolve_route = self._prev_resolver
                client._sink_has_lifecycle = self._prev_has_lifecycle
                client._sink_has_phases = self._prev_has_phases

        return _Ctx()

    async def _make_req(
        self,
        /,
        method: MethodType,
        url: URL,
        handlers: ResponseHandlersType,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
        *,
        operation: str | None = None,
        **kwargs: Any,
    ) -> Any:
        # Быстрый путь: метрики Noop → почти нулевая накладная.
        # ``operation`` НЕ форвардим в super(): базовый _make_req сплатит kwargs
        # в session.request, а aiohttp отвергнет неизвестный аргумент.
        sink = self._metrics_sink
        if isinstance(sink, NoopSink):
            return await super()._make_req(
                method=method,
                url=url,
                handlers=handlers,
                timeout=timeout,
                **kwargs,
            )

        route_label = self._resolve_route(url)
        op = operation or route_label

        # When the sink records network phases, hand the aiohttp TraceConfig
        # callbacks the labels they need. Harmless if no TraceConfig is attached
        # to the session — aiohttp just carries the ctx unused.
        if self._sink_has_phases and "trace_request_ctx" not in kwargs:
            kwargs["trace_request_ctx"] = {
                "client": self._client_name,
                "operation": op,
            }

        start = perf_counter()
        chosen_status: dict[str, int | HTTPStatus | str | None] = {"value": None}

        # Заворачиваем хэндлеры, чтобы знать какой статус сработал
        wrapped_handlers = _wrap_handlers_with_status_mark(handlers, chosen_status)

        error_type: str | None = None
        outcome = "response"
        status_for_metrics: int | str = "unknown"

        if self._sink_has_lifecycle:
            sink.on_request_start(
                client=self._client_name, method=method, route=route_label, operation=op
            )
        try:
            result = await super()._make_req(
                method=method,
                url=url,
                handlers=wrapped_handlers,
                timeout=timeout,
                **kwargs,
            )
            status_for_metrics = _success_status(chosen_status["value"])
            return result
        except BaseException as e:
            status_for_metrics, outcome, error_type = _classify_failure(
                e, chosen_status["value"]
            )
            raise
        finally:
            duration = perf_counter() - start
            if self._sink_has_lifecycle:
                sink.on_request_end(
                    client=self._client_name,
                    method=method,
                    route=route_label,
                    operation=op,
                )
            sink.observe_request(
                client=self._client_name,
                method=method,
                route=route_label,
                operation=op,
                status=status_for_metrics,
                outcome=outcome,
                duration_seconds=duration,
                error_type=error_type,
            )


def _detect_lifecycle(sink: MetricsSink) -> bool:
    return hasattr(sink, "on_request_start") and hasattr(sink, "on_request_end")


def _success_status(value: int | HTTPStatus | str | None) -> int | str:
    if isinstance(value, HTTPStatus):
        return int(value)
    if isinstance(value, int):
        return value
    return "ok"


def _classify_failure(
    exc: BaseException, chosen: int | HTTPStatus | str | None
) -> tuple[int | str, str, str]:
    """Return ``(status, outcome, error_type)`` for a failed request."""
    if isinstance(exc, asyncio.CancelledError):
        outcome, error_type = classify_exception(exc)
        return "none", outcome, error_type

    resp_status = chosen
    if not isinstance(resp_status, int):
        resp_status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if isinstance(resp_status, int):
        # A response arrived; the failure is in handling/deserialization, not the
        # transport. Keep outcome=response so 5xx/latency math on the physical
        # request stays correct.
        return resp_status, "response", "invalid_response"

    outcome, error_type = classify_exception(exc)
    return "none", outcome, error_type


def _wrap_handlers_with_status_mark(
    handlers: ResponseHandlersType,
    chosen_status: dict[str, int | HTTPStatus | str | None],
) -> ResponseHandlersType:
    try:
        wrapped: dict[int | HTTPStatus | str, ResponseHandler] = {}
        for k, handler in handlers.items():
            wrapped[k] = _wrap_one(handler, chosen_status)
        return wrapped
    except AttributeError:
        return handlers


def _wrap_one(
    handler: ResponseHandler,
    chosen_status: dict[str, int | HTTPStatus | str | None],
) -> ResponseHandler:
    async def _wrapped(response: ClientResponse) -> Any:
        chosen_status["value"] = response.status
        return await handler(response)

    return _wrapped
