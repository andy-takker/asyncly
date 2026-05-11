import importlib
import textwrap

import pytest
from aiohttp import ClientSession

from asyncly.srvmocker import JsonResponse, MockRoute
from asyncly.srvmocker.models import MockService

pytest_plugins = ["pytester"]

# The pytest11 entry-point ``asyncly.pytest_plugin`` is imported by pytest
# during plugin discovery, before ``pytest-cov`` has started its tracer. As a
# side effect, ``asyncly/__init__.py`` and the modules it pulls in execute
# their module-level statements untracked. Reload them here so coverage sees
# them, keeping reports consistent with the rest of the suite.
for _module_name in (
    "asyncly.client.typing",
    "asyncly.client.timeout",
    "asyncly.client.handlers.exceptions",
    "asyncly.client.handlers.base",
    "asyncly.client.base",
    "asyncly",
    "asyncly.pytest_plugin",
):
    importlib.reload(importlib.import_module(_module_name))


async def test_default_mock_routes_is_empty(mock_routes: list[MockRoute]) -> None:
    assert list(mock_routes) == []


async def test_mock_service_fixture_runs_in_process(
    mock_service: MockService,
) -> None:
    assert mock_service.url is not None
    assert list(mock_service.history) == []


class TestSuiteOverriddenRoutes:
    @pytest.fixture
    def mock_routes(self) -> list[MockRoute]:
        return [MockRoute("GET", "/ping", "ping")]

    async def test_overridden_routes_served(self, mock_service: MockService) -> None:
        mock_service.register("ping", JsonResponse({"pong": True}))
        async with ClientSession() as session:
            response = await session.get(mock_service.url / "ping")
            body = await response.json()
        assert body == {"pong": True}


def test_mock_service_fixture_is_available(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        textwrap.dedent(
            """
            import pytest
            from aiohttp import ClientSession

            from asyncly.srvmocker import JsonResponse, MockRoute


            @pytest.fixture
            def mock_routes():
                return [MockRoute("GET", "/x", "x")]


            async def test_plugin_provided_service(mock_service):
                mock_service.register("x", JsonResponse({"ok": True}))
                async with ClientSession() as s:
                    resp = await s.get(mock_service.url / "x")
                    body = await resp.json()
                assert body == {"ok": True}
            """
        )
    )
    pytester.makepyprojecttoml(
        textwrap.dedent(
            """
            [tool.pytest.ini_options]
            asyncio_mode = "auto"
            asyncio_default_fixture_loop_scope = "function"
            """
        )
    )
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_no_mock_routes_uses_empty_service(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        textwrap.dedent(
            """
            async def test_default_empty(mock_service):
                assert mock_service.url is not None
                assert list(mock_service.history) == []
            """
        )
    )
    pytester.makepyprojecttoml(
        textwrap.dedent(
            """
            [tool.pytest.ini_options]
            asyncio_mode = "auto"
            asyncio_default_fixture_loop_scope = "function"
            """
        )
    )
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
