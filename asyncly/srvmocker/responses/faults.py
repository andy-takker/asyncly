from collections.abc import Mapping
from http import HTTPStatus

from aiohttp.web_request import Request
from aiohttp.web_response import Response, StreamResponse

from asyncly.srvmocker.responses.base import BaseMockResponse


class DisconnectResponse(BaseMockResponse):
    """Disconnect the socket before response headers are sent."""

    async def response(self, request: Request) -> Response:
        transport = request.transport
        if transport is None:
            raise RuntimeError("request transport is unavailable")
        transport.abort()
        return Response()


class TruncatedResponse(BaseMockResponse):
    """Send fewer body bytes than declared and terminate the connection."""

    def __init__(
        self,
        body: bytes = b"",
        *,
        declared_length: int | None = None,
        status: int = HTTPStatus.OK,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        length = len(body) + 1 if declared_length is None else declared_length
        if length <= len(body):
            raise ValueError("declared_length must be greater than the body length")
        self._body = body
        self._declared_length = length
        self._status = status
        self._headers = dict(headers or {})

    async def response(self, request: Request) -> StreamResponse:
        response = StreamResponse(status=self._status, headers=self._headers)
        response.content_length = self._declared_length
        await response.prepare(request)
        if self._body:
            await response.write(self._body)

        transport = request.transport
        if transport is None:
            raise RuntimeError("request transport is unavailable")
        transport.close()
        return response
