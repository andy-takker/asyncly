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
    """General mock response: a body plus an explicit serializer.

    The format-specific responses (`JsonResponse`, `MsgpackResponse`, ...) are
    thin wrappers over this. Provide a `Serializer` to control the wire format
    and ``Content-Type``.

    Attributes:
        body: The object to serialize (or raw value if no serializer).
        status: HTTP status code to return.
        headers: Extra response headers.
        serializer: Serializer pairing a ``dumps`` callable with a content type.
    """

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
