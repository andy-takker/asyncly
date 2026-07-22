from dataclasses import FrozenInstanceError

import pytest
from aiohttp import ClientSession

import asyncly.srvmocker as srvmocker
from asyncly.srvmocker import MockRoute, RawResponse, start_service


def test_recorded_request_is_public_with_deprecated_alias() -> None:
    assert srvmocker.RecordedRequest
    assert srvmocker.RequestHistory is srvmocker.RecordedRequest


async def test_history_contains_an_immutable_request_snapshot() -> None:
    routes = [MockRoute("POST", "/items/{item_id}", "create_item")]

    async with start_service(routes) as service:
        service.register("create_item", RawResponse())
        async with ClientSession() as session:
            await session.post(
                service.url / "items/42",
                params={"preview": "yes"},
                headers={"X-Request-ID": "request-1"},
                data=b"payload",
            )

        call = service.last_call("create_item")
        assert call.method == "POST"
        assert call.url.path_qs == "/items/42?preview=yes"
        assert call.path == "/items/42"
        assert call.headers["x-request-id"] == "request-1"
        assert call.query["preview"] == "yes"
        assert call.path_params["item_id"] == "42"
        assert call.body == b"payload"
        assert call.handler_name == "create_item"

        with pytest.raises(TypeError):
            call.headers["x-request-id"] = "changed"  # type: ignore[index]
        with pytest.raises(FrozenInstanceError):
            call.body = b"changed"  # type: ignore[misc]
