from collections.abc import Iterable
from typing import Literal

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.exceptions import SequenceExhausted
from asyncly.srvmocker.responses.base import BaseMockResponse

OnExhausted = Literal["raise", "cycle", "last"]


class SequenceResponse(BaseMockResponse):
    """Return a different response on each call, in order.

    ``on_exhausted`` controls behavior after the last response is consumed:

    - ``"raise"`` (default) -- raise :class:`SequenceExhausted` on the next call.
      Inside an aiohttp request handler this surfaces to clients as a 500.
    - ``"cycle"`` -- start over from the first response and loop indefinitely.
    - ``"last"`` -- keep returning the last response forever.

    Constructing with an empty iterable raises ``ValueError`` eagerly.
    """

    def __init__(
        self,
        responses: Iterable[BaseMockResponse],
        on_exhausted: OnExhausted = "raise",
    ) -> None:
        self._responses: list[BaseMockResponse] = list(responses)
        if not self._responses:
            raise ValueError("SequenceResponse requires at least one response")
        self._on_exhausted: OnExhausted = on_exhausted
        self._index = 0

    async def response(self, request: Request) -> Response:
        resp = self._pick()
        return await resp.response(request)

    def _pick(self) -> BaseMockResponse:
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        if self._on_exhausted == "raise":
            raise SequenceExhausted(
                f"SequenceResponse exhausted after {len(self._responses)} response(s)"
            )
        if self._on_exhausted == "cycle":
            resp = self._responses[self._index % len(self._responses)]
            self._index += 1
            return resp
        return self._responses[-1]
