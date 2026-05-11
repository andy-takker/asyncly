import pytest
from aiohttp import ClientSession

from asyncly.srvmocker import JsonResponse, MockRoute, start_service


async def _post_json(url, json):
    async with ClientSession() as s:
        return await s.post(url, json=json)


async def test_get_calls_empty_when_no_requests() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        assert service.get_calls("create") == []


async def test_last_call_returns_latest_request() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        await _post_json(service.url / "x", {"v": 1})
        await _post_json(service.url / "x", {"v": 2})
        last = service.last_call("create")
        assert b'"v": 2' in last.body


async def test_last_call_raises_when_no_calls() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        with pytest.raises(AssertionError, match="no calls"):
            service.last_call("create")


async def test_assert_called_with_json_subset() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        await _post_json(service.url / "x", {"k": "v", "extra": 1})
        service.assert_called("create", json={"k": "v", "extra": 1})


async def test_assert_called_fails_when_no_match() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        await _post_json(service.url / "x", {"k": "v"})
        with pytest.raises(AssertionError):
            service.assert_called("create", json={"k": "other"})


async def test_assert_called_times() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        await _post_json(service.url / "x", {"v": 1})
        await _post_json(service.url / "x", {"v": 2})
        service.assert_called("create", times=2)
        with pytest.raises(AssertionError, match="expected 3"):
            service.assert_called("create", times=3)


async def test_assert_not_called() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        service.assert_not_called("create")
        await _post_json(service.url / "x", {"v": 1})
        with pytest.raises(AssertionError):
            service.assert_not_called("create")


async def test_assert_called_with_body_bytes() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        async with ClientSession() as s:
            await s.post(service.url / "x", data=b"raw-payload")
        service.assert_called("create", body=b"raw-payload")
        with pytest.raises(AssertionError):
            service.assert_called("create", body=b"different")


async def test_assert_called_with_headers_subset() -> None:
    routes = [MockRoute("POST", "/x", "create")]
    async with start_service(routes) as service:
        service.register("create", JsonResponse({}))
        async with ClientSession() as s:
            await s.post(
                service.url / "x",
                headers={"X-Tenant": "acme", "X-Extra": "ok"},
                json={"v": 1},
            )
        service.assert_called("create", headers={"X-Tenant": "acme"})
        with pytest.raises(AssertionError):
            service.assert_called("create", headers={"X-Tenant": "other"})


async def test_assert_called_with_query_subset() -> None:
    routes = [MockRoute("GET", "/x", "list")]
    async with start_service(routes) as service:
        service.register("list", JsonResponse({}))
        async with ClientSession() as s:
            await s.get(service.url / "x", params={"type": "cat", "limit": "5"})
        service.assert_called("list", query={"type": "cat"})
        with pytest.raises(AssertionError):
            service.assert_called("list", query={"type": "dog"})
