from collections.abc import Awaitable, Callable

from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.models import MockService, RequestHistory


def get_default_handler(handler_name: str) -> Callable[[Request], Awaitable[Response]]:
    async def _handler(request: Request) -> Response:
        history = RequestHistory(
            request=request,
            body=await request.read(),
        )
        context: MockService = request.app["service"]
        context.history.append(history)
        context.history_map[handler_name].append(history)
        handler = context.handlers[handler_name]
        return await handler.response(request)

    return _handler
