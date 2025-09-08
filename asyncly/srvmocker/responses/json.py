from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.responses.base import BaseMockResponse
from asyncly.srvmocker.responses.content import ContentResponse
from asyncly.srvmocker.serialization.json import JsonSerializer


class JsonResponse(BaseMockResponse):
    _content: ContentResponse

    def __init__(
        self,
        body: Any,
        status: int = HTTPStatus.OK,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._content = ContentResponse(
            body=body,
            status=status,
            headers=headers,
            serializer=JsonSerializer,
        )

    async def response(self, request: Request) -> Response:
        return await self._content.response(request)
