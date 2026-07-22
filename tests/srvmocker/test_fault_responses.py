from http import HTTPStatus

import pytest
from aiohttp import ClientConnectionError, ClientPayloadError, ClientSession

import asyncly.srvmocker as srvmocker
from asyncly.srvmocker import MockRoute, start_service


def test_fault_responses_are_public() -> None:
    assert srvmocker.DisconnectResponse
    assert srvmocker.TruncatedResponse
    assert srvmocker.LatencyResponse


async def test_disconnect_response_closes_before_headers() -> None:
    routes = [MockRoute("GET", "/fault", "fault")]

    async with start_service(routes) as service:
        service.register("fault", srvmocker.DisconnectResponse())
        async with ClientSession() as session:
            with pytest.raises(ClientConnectionError):
                await session.get(service.url / "fault")


async def test_truncated_response_fails_while_reading_body() -> None:
    routes = [MockRoute("GET", "/fault", "fault")]

    async with start_service(routes) as service:
        service.register(
            "fault",
            srvmocker.TruncatedResponse(
                body=b"partial",
                declared_length=20,
            ),
        )
        async with ClientSession() as session:
            response = await session.get(service.url / "fault")
            assert response.status == HTTPStatus.OK
            with pytest.raises(ClientPayloadError):
                await response.read()
