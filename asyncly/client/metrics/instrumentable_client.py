from http import HTTPStatus
from time import perf_counter
from types import TracebackType
from typing import Any

from aiohttp import ClientResponse, ClientSession
from aiohttp.client import DEFAULT_TIMEOUT
from yarl import URL

from asyncly.client.base import BaseHttpClient, MethodType
from asyncly.client.metrics.route_resolver import default_route_resolver
from asyncly.client.metrics.sinks.base import MetricsSink
from asyncly.client.metrics.sinks.noop import NoopSink
from asyncly.client.timeout import TimeoutType
from asyncly.client.typing import ResponseHandler, ResponseHandlersType, RouteResolver


class InstrumentableHttpClient(BaseHttpClient):
    __slots__ = ("_metrics_sink", "_resolve_route") + BaseHttpClient.__slots__

    def __init__(
        self,
        url: URL | str,
        session: ClientSession,
        client_name: str,
    ) -> None:
        super().__init__(url=url, session=session, client_name=client_name)
        self._metrics_sink: MetricsSink = NoopSink()
        self._resolve_route: RouteResolver = default_route_resolver

    def enable_metrics(
        self, sink: MetricsSink, *, route_resolver: RouteResolver | None = None
    ) -> None:
        self._metrics_sink = sink
        if route_resolver is not None:
            self._resolve_route = route_resolver

    def disable_metrics(self) -> None:
        self._metrics_sink = NoopSink()
        self._resolve_route = default_route_resolver

    def instrument(  # type: ignore[no-untyped-def]
        self, sink: MetricsSink, *, route_resolver: RouteResolver | None = None
    ):
        client = self

        class _Ctx:
            def __enter__(self) -> "InstrumentableHttpClient":
                self._prev_sink = client._metrics_sink
                self._prev_resolver = client._resolve_route
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

        return _Ctx()

    async def _make_req(
        self,
        /,
        method: MethodType,
        url: URL,
        handlers: ResponseHandlersType,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> Any:
        # Быстрый путь: метрики Noop → почти нулевая накладная
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
        start = perf_counter()
        chosen_status: dict[str, int | HTTPStatus | str | None] = {"value": None}

        # Заворачиваем хэндлеры, чтобы знать какой статус сработал
        wrapped_handlers = _wrap_handlers_with_status_mark(handlers, chosen_status)

        error_type: str | None = None
        status_for_metrics: int | str = "unknown"
        try:
            result = await super()._make_req(
                method=method, url=url, handlers=wrapped_handlers, timeout=timeout
            )
            v = chosen_status["value"]
            if isinstance(v, HTTPStatus):
                status_for_metrics = int(v)
            elif isinstance(v, int):
                status_for_metrics = v
            else:
                status_for_metrics = "ok"
            return result
        except Exception as e:
            status = (
                chosen_status["value"]
                or getattr(e, "status", None)
                or getattr(e, "status_code", None)
            )
            status_for_metrics = int(status) if isinstance(status, int) else "exception"
            error_type = type(e).__name__
            raise
        finally:
            duration = perf_counter() - start
            sink.observe_request(
                client=self._client_name,
                method=method,
                route=route_label,
                status=status_for_metrics,
                duration_seconds=duration,
                error_type=error_type,
            )


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
