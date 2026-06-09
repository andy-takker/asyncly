"""Pytest plugin exposing `mock_routes` and `mock_service` fixtures.

Users override `mock_routes` to declare the test server's API surface:

    @pytest.fixture
    def mock_routes():
        return [MockRoute("GET", "/x", "x")]

    async def test_x(mock_service):
        mock_service.register("x", JsonResponse({"ok": True}))
        ...
"""

from collections.abc import AsyncIterator, Iterable
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from asyncly.srvmocker.models import MockRoute, MockService
    from asyncly.srvmocker.proxy import MockProxyService


@pytest.fixture
def mock_routes() -> "Iterable[MockRoute]":
    """Override in tests to declare routes for `mock_service`."""
    return []


@pytest.fixture
async def mock_service(
    mock_routes: "Iterable[MockRoute]",
) -> "AsyncIterator[MockService]":
    from asyncly.srvmocker import start_service

    async with start_service(mock_routes) as service:
        yield service


@pytest.fixture
async def mock_proxy() -> "AsyncIterator[MockProxyService]":
    """A forwarding mock proxy; point a client at it via ``proxy=mock_proxy.url``."""
    from asyncly.srvmocker import start_proxy

    async with start_proxy() as proxy:
        yield proxy
