from asyncio import sleep
from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from aiohttp import hdrs
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.models import BaseMockResponse
from asyncly.srvmocker.serialization import JsonSerializer, Serializer

TimeoutType = int | float


@dataclass
class ContentResponse(BaseMockResponse):
    body: Any = None
    status: int = HTTPStatus.OK
    headers: Mapping[str, str] | None = None
    serializer: Serializer | None = None

    async def response(self, request: Request) -> Response:
        headers: MutableMapping[str, str] = dict()
        if self.headers:
            headers.update(self.headers)
        if self.serializer:
            headers[hdrs.CONTENT_TYPE] = self.serializer.content_type
        return Response(
            status=self.status,
            body=self.serialize(),
            headers=headers,
        )

    def serialize(self) -> Any:
        if not self.serializer:
            return self.body
        return self.serializer.dumps(self.body)


@dataclass
class LatencyResponse(BaseMockResponse):
    wrapped: BaseMockResponse
    latency: TimeoutType

    async def response(self, request: Request) -> Response:
        await sleep(self.latency)
        return await self.wrapped.response(request)


class MockSeqResponse(BaseMockResponse):
    responses: Iterator[BaseMockResponse]

    def __init__(self, responses: Iterable[BaseMockResponse]) -> None:
        self.responses = iter(responses)

    async def response(self, request: Request) -> Response:
        resp = next(self.responses)
        return await resp.response(request)


class JsonResponse(BaseMockResponse):
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
            serializer=JsonSerializer,
        )

    async def response(self, request: Request) -> Response:
        return await self.__content.response(request)
