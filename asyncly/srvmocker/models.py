from abc import ABC, abstractmethod
from collections.abc import MutableMapping, MutableSequence
from dataclasses import dataclass

from aiohttp.web_request import Request
from aiohttp.web_response import Response
from yarl import URL


@dataclass(frozen=True)
class MockRoute:
    method: str
    path: str
    handler_name: str


@dataclass
class RequestHistory:
    request: Request
    body: bytes


class BaseMockResponse(ABC):
    @abstractmethod
    async def response(self, request: Request) -> Response:
        pass


@dataclass(frozen=True)
class MockService:
    history: MutableSequence[RequestHistory]
    history_map: MutableMapping[str, MutableSequence[RequestHistory]]
    url: URL
    handlers: MutableMapping[str, BaseMockResponse]

    def register(self, name: str, resp: BaseMockResponse) -> None:
        self.handlers[name] = resp
