from http import HTTPStatus

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.responses.base import BaseMockResponse


class RawResponse(BaseMockResponse):
    """Return arbitrary bytes with arbitrary headers — useful for testing client
    behavior on malformed data, unexpected content-types, or empty bodies.
    """

    def __init__(
        self,
        body: bytes = b"",
        status: int = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._body = body
        self._status = status
        self._headers = headers or {}

    async def response(self, request: Request) -> Response:
        return Response(body=self._body, status=self._status, headers=self._headers)
