import json

import pytest
from aiohttp import ClientSession

from asyncly.srvmocker import MockRoute, RawResponse, start_service


async def test_raw_response_returns_arbitrary_bytes() -> None:
    routes = [MockRoute("GET", "/x", "raw")]
    async with start_service(routes) as service:
        service.register(
            "raw",
            RawResponse(
                body=b"{not valid json",
                status=200,
                headers={"Content-Type": "application/json"},
            ),
        )
        async with ClientSession() as s:
            resp = await s.get(service.url / "x")
            text = await resp.text()
    assert text == "{not valid json"
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)


async def test_raw_response_default_status_and_empty_body() -> None:
    routes = [MockRoute("GET", "/x", "raw")]
    async with start_service(routes) as service:
        service.register("raw", RawResponse())
        async with ClientSession() as s:
            resp = await s.get(service.url / "x")
    assert resp.status == 200
    assert await resp.read() == b""
