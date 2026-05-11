from collections.abc import Awaitable, Callable, Sequence

from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from asyncly.srvmocker.constants import SERVICE_KEY
from asyncly.srvmocker.models import MockRoute, MockService, RequestHistory


def build_dispatcher(
    routes: Sequence[MockRoute],
) -> Callable[[Request], Awaitable[Response]]:
    """Build an aiohttp handler that dispatches across routes sharing (method, path)."""

    async def _dispatch(request: Request) -> Response:
        body = await request.read()
        context: MockService = request.app[SERVICE_KEY]

        chosen: MockRoute | None = None
        for route in routes:
            if route.match is None or route.match.matches(request, body):
                chosen = route
                break

        if chosen is None:
            raise HTTPNotFound(reason="No MockRoute matched the request")

        history = RequestHistory(request=request, body=body)
        context.history.append(history)
        context.history_map[chosen.handler_name].append(history)
        handler = context.handlers[chosen.handler_name]
        return await handler.response(request)

    return _dispatch
