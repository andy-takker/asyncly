from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from aiohttp import hdrs
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.responses.base import BaseMockResponse
from asyncly.srvmocker.serialization.base import Serializer


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
