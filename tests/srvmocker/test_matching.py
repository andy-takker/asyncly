from collections.abc import AsyncIterator

import pytest
from aiohttp import ClientSession

from asyncly.srvmocker import (
    JsonResponse,
    Match,
    MockRoute,
    start_service,
)
from asyncly.srvmocker.models import MockService


@pytest.fixture
async def matched_service() -> AsyncIterator[MockService]:
    routes = [
        MockRoute("POST", "/items", "create_a", match=Match(json={"kind": "a"})),
        MockRoute("POST", "/items", "create_b", match=Match(json={"kind": "b"})),
        MockRoute("POST", "/items", "create_default"),
    ]
    async with start_service(routes) as service:
        service.register("create_a", JsonResponse({"id": 1}))
        service.register("create_b", JsonResponse({"id": 2}))
        service.register("create_default", JsonResponse({"id": 0}))
        yield service


async def test_match_routes_by_json_body(matched_service: MockService) -> None:
    async with ClientSession() as s:
        r1 = await (
            await s.post(matched_service.url / "items", json={"kind": "a"})
        ).json()
        r2 = await (
            await s.post(matched_service.url / "items", json={"kind": "b"})
        ).json()
        r3 = await (
            await s.post(matched_service.url / "items", json={"kind": "c"})
        ).json()
    assert (r1, r2, r3) == ({"id": 1}, {"id": 2}, {"id": 0})


async def test_match_by_headers_subset() -> None:
    routes = [
        MockRoute("GET", "/x", "auth", match=Match(headers={"X-Tenant": "acme"})),
        MockRoute("GET", "/x", "noauth"),
    ]
    async with start_service(routes) as service:
        service.register("auth", JsonResponse({"who": "acme"}))
        service.register("noauth", JsonResponse({"who": "guest"}))
        async with ClientSession() as s:
            r = await (
                await s.get(
                    service.url / "x", headers={"X-Tenant": "acme", "X-Extra": "ok"}
                )
            ).json()
    assert r == {"who": "acme"}


async def test_match_by_query_subset() -> None:
    routes = [
        MockRoute("GET", "/x", "filtered", match=Match(query={"type": "cat"})),
        MockRoute("GET", "/x", "all"),
    ]
    async with start_service(routes) as service:
        service.register("filtered", JsonResponse({"only": "cats"}))
        service.register("all", JsonResponse({"all": True}))
        async with ClientSession() as s:
            r = await (
                await s.get(service.url / "x", params={"type": "cat", "limit": "5"})
            ).json()
    assert r == {"only": "cats"}


async def test_no_match_no_fallback_returns_404() -> None:
    routes = [MockRoute("POST", "/items", "specific", match=Match(json={"kind": "a"}))]
    async with start_service(routes) as service:
        service.register("specific", JsonResponse({"ok": True}))
        async with ClientSession() as s:
            resp = await s.post(service.url / "items", json={"kind": "z"})
    assert resp.status == 404


async def test_match_by_body_bytes() -> None:
    routes = [
        MockRoute("POST", "/raw", "matched", match=Match(body=b"hello")),
        MockRoute("POST", "/raw", "fallback"),
    ]
    async with start_service(routes) as service:
        service.register("matched", JsonResponse({"matched": True}))
        service.register("fallback", JsonResponse({"matched": False}))
        async with ClientSession() as s:
            r1 = await (await s.post(service.url / "raw", data=b"hello")).json()
            r2 = await (await s.post(service.url / "raw", data=b"world")).json()
    assert (r1, r2) == ({"matched": True}, {"matched": False})


async def test_first_matching_route_wins_in_registration_order() -> None:
    # Both routes would match a request without any discriminator, since
    # match=None is a fallback. The first declared one must win.
    routes = [
        MockRoute("GET", "/x", "first"),
        MockRoute("GET", "/x", "second"),
    ]
    async with start_service(routes) as service:
        service.register("first", JsonResponse({"who": "first"}))
        service.register("second", JsonResponse({"who": "second"}))
        async with ClientSession() as s:
            r = await (await s.get(service.url / "x")).json()
    assert r == {"who": "first"}
