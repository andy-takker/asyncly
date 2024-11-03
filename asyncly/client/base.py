from typing import Any, Literal

from aiohttp import ClientSession
from aiohttp.client import DEFAULT_TIMEOUT
from yarl import URL

from asyncly.client.handlers.base import (
    ResponseHandlersType,
    apply_handler,
)
from asyncly.client.timeout import TimeoutType, get_timeout


class BaseHttpClient:
    __slots__ = ("_url", "_session", "_client_name")

    _url: URL
    _session: ClientSession
    _client_name: str

    def __init__(
        self, url: URL | str, session: ClientSession, client_name: str
    ) -> None:
        self._url = url if isinstance(url, URL) else URL(url)
        self._session = session
        self._client_name = client_name

    @property
    def url(self) -> URL:
        return self._url

    async def _make_req(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"],
        url: URL,
        handlers: ResponseHandlersType,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> Any:
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
