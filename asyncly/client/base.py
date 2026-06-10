from typing import Any

from aiohttp import BasicAuth, ClientSession
from aiohttp.client import DEFAULT_TIMEOUT
from yarl import URL

from asyncly.client.handlers.base import (
    ResponseHandlersType,
    apply_handler,
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
        async with self._session.request(
            method=method,
            url=url,
            timeout=get_timeout(timeout),
            **kwargs,
        ) as response:
            return await apply_handler(
                handlers=handlers,
                response=response,
                client_name=self._client_name,
            )
