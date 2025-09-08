from collections.abc import MutableMapping, MutableSequence
from dataclasses import dataclass

from aiohttp.web_request import Request
from yarl import URL

from asyncly.srvmocker.responses.base import BaseMockResponse


@dataclass(frozen=True)
class MockRoute:
    method: str
    path: str
    handler_name: str


@dataclass
class RequestHistory:
    request: Request
    body: bytes


@dataclass(frozen=True)
class MockService:
    history: MutableSequence[RequestHistory]
    history_map: MutableMapping[str, MutableSequence[RequestHistory]]
    url: URL
    handlers: MutableMapping[str, BaseMockResponse]

    def register(self, name: str, resp: BaseMockResponse) -> None:
        self.handlers[name] = resp

    def set_url(self, url: URL) -> None:
        object.__setattr__(self, "url", url)
