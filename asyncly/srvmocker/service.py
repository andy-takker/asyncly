from collections import defaultdict
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from ssl import SSLContext

from aiohttp.test_utils import TestServer
from aiohttp.web_app import Application
from yarl import URL

from asyncly.srvmocker.constants import SERVICE_KEY
from asyncly.srvmocker.handlers import build_dispatcher
from asyncly.srvmocker.models import MockRoute, MockService


@asynccontextmanager
async def start_service(
    routes: Iterable[MockRoute],
    *,
    ssl_context: SSLContext | None = None,
) -> AsyncGenerator[MockService, None]:
    """Start a real `aiohttp.TestServer` for the given routes.

    An async context manager. On enter it binds the server to a free port and
    yields a [`MockService`][asyncly.srvmocker.MockService] whose ``url`` points
    at it; on exit it shuts the server down.

    Args:
        routes: The routes to serve. Several routes may share a
            ``(method, path)`` and be disambiguated by their
            [`Match`][asyncly.srvmocker.Match].
        ssl_context: If given, serve over HTTPS; ``service.url`` then reports
            ``scheme="https"``.

    Yields:
        MockService: Handle to register responses and assert on requests.

    Example:
        ```python
        async with start_service([MockRoute("GET", "/x", "ok")]) as service:
            service.register("ok", JsonResponse({"ok": True}))
        ```
    """
    app = Application()
    routes_list = list(routes)
    handler_names = frozenset(r.handler_name for r in routes_list)
    mock_service = MockService(
        history=list(),
        history_map=defaultdict(list),
        url=URL(),
        handlers=dict(),
        _handler_names=handler_names,
    )
    app[SERVICE_KEY] = mock_service

    groups: dict[tuple[str, str], list[MockRoute]] = defaultdict(list)
    for route in routes_list:
        groups[(route.method, route.path)].append(route)
    for (method, path), group in groups.items():
        app.router.add_route(method=method, path=path, handler=build_dispatcher(group))

    server = TestServer(app)
    await server.start_server(ssl=ssl_context)
    mock_service.set_url(server.make_url(""))
    try:
        yield mock_service
    finally:
        await server.close()
