import asyncio
from collections.abc import AsyncIterable, Mapping, Sequence
from dataclasses import replace
from typing import Any, NoReturn

from aiohttp import (
    BasicAuth,
    ClientHandlerType,
    ClientOSError,
    ClientRequest,
    ClientResponse,
    ClientSession,
    ServerDisconnectedError,
)
from aiohttp.client import DEFAULT_TIMEOUT
from yarl import URL

from asyncly.client.handlers.base import (
    ResponseHandlersType,
    apply_handler,
)
from asyncly.client.retry import (
    RetryContext,
    RetryEvent,
    RetryObserver,
    RetryPolicy,
    _RetryableResponse,
)
from asyncly.client.timeout import TimeoutType, get_timeout
from asyncly.client.typing import MethodType


class BaseHttpClient:
    """Typed base class for building async HTTP API clients.

    Subclass it and add one method per endpoint, delegating to ``_make_req``
    with a mapping of status codes to response handlers. The
    `aiohttp.ClientSession` is injected, so connection pooling and lifecycle
    stay under your control.

    Example:
        ```python
        class CatfactClient(BaseHttpClient):
            FACT_HANDLERS = MappingProxyType({HTTPStatus.OK: parse_model(CatFact)})

            async def fetch_fact(self) -> CatFact:
                return await self._make_req(
                    method=hdrs.METH_GET,
                    url=self._url / "fact",
                    handlers=self.FACT_HANDLERS,
                )
        ```
    """

    __slots__ = ("_url", "_session", "_client_name", "_proxy", "_proxy_auth")

    _url: URL
    _session: ClientSession
    _client_name: str
    _proxy: URL | None
    _proxy_auth: BasicAuth | None

    def __init__(
        self,
        url: URL | str,
        session: ClientSession,
        client_name: str,
        *,
        proxy: URL | str | None = None,
        proxy_auth: BasicAuth | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            url: Base URL the client's endpoints are resolved against.
            session: The `aiohttp.ClientSession` to issue requests with. The
                caller owns its lifecycle.
            client_name: Identifier used in metrics labels and error messages.
            proxy: Default proxy URL for every request. Can be overridden
                per request by passing `proxy=` to `_make_req`.
            proxy_auth: Default `BasicAuth` credentials for the proxy.
        """
        self._url = url if isinstance(url, URL) else URL(url)
        self._session = session
        self._client_name = client_name
        self._proxy = URL(proxy) if isinstance(proxy, str) else proxy
        self._proxy_auth = proxy_auth

    @property
    def url(self) -> URL:
        """The base URL the client was configured with."""
        return self._url

    async def _make_req(
        self,
        method: MethodType,
        url: URL,
        handlers: ResponseHandlersType,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
        *,
        retry: RetryPolicy | None = None,
        retry_observer: RetryObserver | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Issue a request and dispatch the response to a status handler.

        Args:
            method: HTTP method, e.g. `aiohttp.hdrs.METH_GET`.
            url: Fully resolved request URL.
            handlers: Mapping of status code (exact, ``"2xx"`` range, or ``"*"``
                wildcard) to a response handler callable.
            timeout: Per-request timeout; accepts `ClientTimeout`, `timedelta`,
                or a number of seconds.
            retry: Optional retry policy. Without one, a single physical request
                is made exactly as in previous releases.
            retry_observer: Optional synchronous callback for retry decisions.
            operation: Logical operation label used by instrumented clients.
            **kwargs: Extra arguments forwarded to `ClientSession.request`
                (e.g. ``json``, ``params``, ``headers``). Instance-level
                ``proxy`` / ``proxy_auth`` are injected here unless overridden.

        Returns:
            Whatever the matched handler returns.

        Raises:
            UnhandledStatusException: If no handler matches the response status.
        """
        if "proxy" not in kwargs and self._proxy is not None:
            kwargs["proxy"] = self._proxy
        if "proxy_auth" not in kwargs and self._proxy_auth is not None:
            kwargs["proxy_auth"] = self._proxy_auth

        if retry is None:
            return await self._request_once(
                method=method,
                url=url,
                handlers=handlers,
                timeout=timeout,
                operation=operation,
                **kwargs,
            )

        replayable = _is_request_replayable(kwargs)
        for attempt in range(1, retry.max_attempts + 1):
            context = RetryContext(
                method=str(method),
                url=url,
                attempt=attempt,
                max_attempts=retry.max_attempts,
                replayable=replayable,
            )
            try:
                result = await self._request_once(
                    method=method,
                    url=url,
                    handlers=handlers,
                    timeout=timeout,
                    operation=operation,
                    retry=retry,
                    retry_context=context,
                    retry_observer=retry_observer,
                    **kwargs,
                )
            except Exception as exc:  # noqa: BLE001 - policy owns exception filters
                delay = _retry_exception_delay(
                    policy=retry,
                    context=context,
                    observer=retry_observer,
                    caught=exc,
                )
                await asyncio.sleep(delay)
                continue

            if not isinstance(result, _RetryableResponse):
                return result

            delay = retry.get_delay(
                result.context,
                retry_after=result.retry_after,
            )
            _notify_retry_observer(
                retry_observer,
                RetryEvent(
                    kind="scheduled",
                    context=result.context,
                    delay=delay,
                    reason="status",
                ),
            )
            await asyncio.sleep(delay)

        raise RuntimeError("retry loop exited without a result")

    async def _request_once(
        self,
        *,
        method: MethodType,
        url: URL,
        handlers: ResponseHandlersType,
        timeout: TimeoutType,
        operation: str | None = None,
        retry: RetryPolicy | None = None,
        retry_context: RetryContext | None = None,
        retry_observer: RetryObserver | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute and handle one physical HTTP request."""

        if retry is not None:
            user_middlewares = kwargs.get("middlewares") or ()
            kwargs["middlewares"] = (
                _expose_aiohttp_transport_errors,
                *user_middlewares,
            )

        async with self._session.request(
            method=method,
            url=url,
            timeout=get_timeout(timeout),
            **kwargs,
        ) as response:
            if retry is not None and retry_context is not None:
                response_context = replace(
                    retry_context,
                    response_status=response.status,
                )
                if retry._matches_outcome(response_context):
                    suppression = retry._suppression_reason(response_context)
                    if suppression is None:
                        return _RetryableResponse(
                            context=response_context,
                            retry_after=response.headers.get("Retry-After"),
                        )
                    _notify_retry_observer(
                        retry_observer,
                        RetryEvent(
                            kind=(
                                "exhausted"
                                if suppression == "attempts_exhausted"
                                else "suppressed"
                            ),
                            context=response_context,
                            reason=suppression,
                        ),
                    )
            return await apply_handler(
                handlers=handlers,
                response=response,
                client_name=self._client_name,
            )


class _ObservableTransportError(Exception):
    def __init__(
        self,
        original: ClientOSError | ServerDisconnectedError,
    ) -> None:
        super().__init__(str(original))
        self.original = original


async def _expose_aiohttp_transport_errors(
    request: ClientRequest,
    handler: ClientHandlerType,
) -> ClientResponse:
    try:
        return await handler(request)
    except (ClientOSError, ServerDisconnectedError) as exc:
        # aiohttp otherwise retries these internally for idempotent methods.
        # Wrapping here makes every socket attempt visible to Asyncly's policy,
        # observer, and instrumentation. The wrapper is unwrapped before it can
        # escape the client.
        raise _ObservableTransportError(exc) from exc


def _notify_retry_observer(
    observer: RetryObserver | None,
    event: RetryEvent,
) -> None:
    if observer is not None:
        observer(event)


def _unwrap_observable_transport_error(caught: BaseException) -> BaseException:
    if isinstance(caught, _ObservableTransportError):
        return caught.original
    return caught


def _retry_exception_delay(
    *,
    policy: RetryPolicy,
    context: RetryContext,
    observer: RetryObserver | None,
    caught: BaseException,
) -> float:
    original = _unwrap_observable_transport_error(caught)
    failed_context = replace(context, exception=original)
    if not policy._matches_outcome(failed_context):
        _raise_original(caught, original)

    suppression = policy._suppression_reason(failed_context)
    if suppression is not None:
        _notify_retry_observer(
            observer,
            RetryEvent(
                kind=(
                    "exhausted" if suppression == "attempts_exhausted" else "suppressed"
                ),
                context=failed_context,
                reason=suppression,
            ),
        )
        _raise_original(caught, original)

    delay = policy.get_delay(failed_context)
    _notify_retry_observer(
        observer,
        RetryEvent(
            kind="scheduled",
            context=failed_context,
            delay=delay,
            reason="exception",
        ),
    )
    return delay


def _raise_original(caught: BaseException, original: BaseException) -> NoReturn:
    if original is caught:
        raise caught.with_traceback(caught.__traceback__)
    raise original.with_traceback(original.__traceback__)


def _is_request_replayable(kwargs: Mapping[str, Any]) -> bool:
    if "data" not in kwargs:
        return True
    return _is_replayable_data(kwargs["data"])


def _is_replayable_data(data: Any) -> bool:
    if data is None or isinstance(
        data,
        str | bytes | bytearray | memoryview | int | float | bool,
    ):
        return True
    if isinstance(data, Mapping):
        return all(_is_replayable_data(value) for value in data.values())
    if isinstance(data, Sequence):
        return all(
            isinstance(item, Sequence)
            and not isinstance(item, str | bytes | bytearray | memoryview)
            and len(item) == 2
            and _is_replayable_data(item[1])
            for item in data
        )
    if isinstance(data, AsyncIterable):
        return False
    return False
