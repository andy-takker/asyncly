from asyncio import sleep
from dataclasses import dataclass

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.responses.base import BaseMockResponse

TimeoutType = int | float


@dataclass
class LatencyResponse(BaseMockResponse):
    """Delay another response by a fixed latency — for testing timeouts.

    Attributes:
        wrapped: The response to return after the delay.
        latency: Delay in seconds before responding.
    """

    wrapped: BaseMockResponse
    latency: TimeoutType

    async def response(self, request: Request) -> Response:
        await sleep(self.latency)
        return await self.wrapped.response(request)
