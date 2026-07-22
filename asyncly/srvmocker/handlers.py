from collections.abc import Awaitable, Callable, Sequence

from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse

from asyncly.srvmocker.constants import SERVICE_KEY
from asyncly.srvmocker.exceptions import MissingResponseError
from asyncly.srvmocker.models import MockRoute, MockService, RecordedRequest


def build_dispatcher(
    routes: Sequence[MockRoute],
) -> Callable[[Request], Awaitable[StreamResponse]]:
    """Build an aiohttp handler that dispatches across routes sharing (method, path)."""

    async def _dispatch(request: Request) -> StreamResponse:
        body = await request.read()
        context: MockService = request.app[SERVICE_KEY]

        chosen: MockRoute | None = None
        for route in routes:
            if route.match is None or route.match.matches(request, body):
                chosen = route
                break

        if chosen is None:
            raise HTTPNotFound(reason="No MockRoute matched the request")

        recorded = RecordedRequest(
            method=request.method,
            url=request.url,
            path=request.path,
            headers=request.headers,
            query=request.query,
            path_params=request.match_info,
            body=body,
            handler_name=chosen.handler_name,
        )
        context.history.append(recorded)
        context.history_map[chosen.handler_name].append(recorded)
        handler = context.handlers.get(chosen.handler_name)
        if handler is None:
            raise MissingResponseError(
                f"no response registered for handler {chosen.handler_name!r}; "
                f"call service.register({chosen.handler_name!r}, response)"
            )
        return await handler.response(request)

    return _dispatch
