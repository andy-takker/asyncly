from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.responses.base import BaseMockResponse
from asyncly.srvmocker.responses.content import ContentResponse
from asyncly.srvmocker.serialization.msgpack import MsgpackSerializer


class MsgpackResponse(BaseMockResponse):
    __content: ContentResponse

    def __init__(
        self,
        body: Any,
        status: int = HTTPStatus.OK,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.__content = ContentResponse(
            body=body,
            status=status,
            headers=headers,
            serializer=MsgpackSerializer,
        )

    async def response(self, request: Request) -> Response:
        return await self.__content.response(request)
