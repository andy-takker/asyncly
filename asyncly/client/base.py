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
        self._url = url if isinstance(url, URL) else URL(url)
        self._session = session
        self._client_name = client_name
        self._proxy = URL(proxy) if isinstance(proxy, str) else proxy
        self._proxy_auth = proxy_auth

    @property
    def url(self) -> URL:
        return self._url

    async def _make_req(
        self,
        method: MethodType,
        url: URL,
        handlers: ResponseHandlersType,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> Any:
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
