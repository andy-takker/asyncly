from abc import ABC, abstractmethod

from aiohttp.web_request import Request
from aiohttp.web_response import Response


class BaseMockResponse(ABC):
    @abstractmethod
    async def response(self, request: Request) -> Response:
        pass
