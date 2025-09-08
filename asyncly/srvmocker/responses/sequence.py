from collections.abc import Iterable, Iterator

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.responses.base import BaseMockResponse


class SequenceResponse(BaseMockResponse):
    responses: Iterator[BaseMockResponse]

    def __init__(self, responses: Iterable[BaseMockResponse]) -> None:
        self.responses = iter(responses)

    async def response(self, request: Request) -> Response:
        resp = next(self.responses)
        return await resp.response(request)
