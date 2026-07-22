import warnings
from http import HTTPStatus

import pytest
from aiohttp import ClientSession

import asyncly.srvmocker as srvmocker
from asyncly.srvmocker import (
    JsonResponse,
    MockRoute,
    UnknownHandlerError,
    start_service,
)


async def test_register_unknown_name_raises_typed_error() -> None:
    routes = [MockRoute("GET", "/x", "known")]
    async with start_service(routes) as service:
        with pytest.raises(UnknownHandlerError, match="unknown handler_name"):
            service.register("typo", JsonResponse({}))
        assert "typo" not in service.handlers


async def test_register_known_name_emits_no_warning() -> None:
    routes = [MockRoute("GET", "/x", "known")]
    async with start_service(routes) as service:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            service.register("known", JsonResponse({}))


async def test_missing_response_is_reported_with_handler_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    routes = [MockRoute("GET", "/x", "known")]

    async with start_service(routes) as service:
        async with ClientSession() as session:
            response = await session.get(service.url / "x")

    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "MissingResponseError" in caplog.text
    assert "known" in caplog.text
    assert srvmocker.MissingResponseError
