from abc import ABC, abstractmethod

from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse


class BaseMockResponse(ABC):
    @abstractmethod
    async def response(self, request: Request) -> StreamResponse:
        pass
