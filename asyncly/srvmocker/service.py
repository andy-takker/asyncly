from collections import defaultdict
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager

from aiohttp.test_utils import TestServer
from aiohttp.web_app import Application

from asyncly.srvmocker.handlers import get_default_handler
from asyncly.srvmocker.models import MockRoute, MockService


@asynccontextmanager
async def start_service(
    routes: Iterable[MockRoute],
) -> AsyncGenerator[MockService, None]:
    app = Application()
    server = TestServer(app)
    for route in routes:
        app.router.add_route(
            method=route.method,
            path=route.path,
            handler=get_default_handler(route.handler_name),
        )
    await server.start_server()
    mock_service = MockService(
        history=list(),
        history_map=defaultdict(list),
        url=server.make_url(""),
        handlers=dict(),
    )
    app["service"] = mock_service
    try:
        yield mock_service
    finally:
        await server.close()
