from http import HTTPStatus
from types import MappingProxyType

import pytest
from aiohttp import BasicAuth, ClientSession, hdrs, web
from aiohttp.test_utils import RawTestServer

from asyncly import BaseHttpClient, ResponseHandlersType
from asyncly.client.handlers.json import parse_json
from asyncly.srvmocker import (
    JsonResponse,
    MockProxyService,
    MockRoute,
    RawResponse,
    start_proxy,
    start_service,
)


class _Client(BaseHttpClient):
    HANDLERS: ResponseHandlersType = MappingProxyType(
        {HTTPStatus.OK: parse_json(lambda data: data)}
    )

    async def fetch(self) -> object:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "x",
            handlers=self.HANDLERS,
        )


async def test_proxy_forwards_to_target() -> None:
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy() as proxy:
            async with ClientSession() as s:
                resp = await s.get(target.url / "x", proxy=proxy.url)
                payload = await resp.json()

    assert payload == {"ok": True}
    target.assert_called("ok", times=1)
    proxy.assert_called(times=1, method="GET", target=str(target.url / "x"))


async def test_client_proxy_constructor_arg() -> None:
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy() as proxy:
            async with ClientSession() as session:
                client = _Client(
                    url=target.url,
                    session=session,
                    client_name="test",
                    proxy=proxy.url,
                )
                result = await client.fetch()

    assert result == {"ok": True}
    proxy.assert_called(times=1, method="GET")


async def test_client_per_request_proxy_override() -> None:
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy() as used, start_proxy() as unused:
            async with ClientSession() as session:
                # Construct with `unused` proxy, override per-request with `used`.
                client = _Client(
                    url=target.url,
                    session=session,
                    client_name="test",
                    proxy=unused.url,
                )
                await client._make_req(
                    method=hdrs.METH_GET,
                    url=target.url / "x",
                    handlers=_Client.HANDLERS,
                    proxy=used.url,
                )

    used.assert_called(times=1)
    unused.assert_not_called()


async def test_proxy_auth_success() -> None:
    auth = BasicAuth("user", "secret")
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy(auth=auth) as proxy:
            async with ClientSession() as s:
                resp = await s.get(target.url / "x", proxy=proxy.url, proxy_auth=auth)
                payload = await resp.json()

    assert payload == {"ok": True}
    proxy.assert_called(
        times=1,
        headers={"Proxy-Authorization": auth.encode()},
    )


async def test_client_proxy_auth_constructor_arg() -> None:
    # `proxy_auth` set on the client is injected and reaches the proxy.
    auth = BasicAuth("user", "secret")
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy(auth=auth) as proxy:
            async with ClientSession() as session:
                client = _Client(
                    url=target.url,
                    session=session,
                    client_name="test",
                    proxy=proxy.url,
                    proxy_auth=auth,
                )
                result = await client.fetch()

    assert result == {"ok": True}
    proxy.assert_called(
        times=1,
        headers={"Proxy-Authorization": auth.encode()},
    )


async def test_proxy_auth_missing_returns_407() -> None:
    auth = BasicAuth("user", "secret")
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy(auth=auth) as proxy:
            async with ClientSession() as s:
                resp = await s.get(target.url / "x", proxy=proxy.url)
                status = resp.status

    assert status == HTTPStatus.PROXY_AUTHENTICATION_REQUIRED
    # Request was recorded, but never forwarded to the target.
    proxy.assert_called(times=1)
    target.assert_not_called("ok")


async def test_proxy_auth_wrong_returns_407() -> None:
    auth = BasicAuth("user", "secret")
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy(auth=auth) as proxy:
            async with ClientSession() as s:
                resp = await s.get(
                    target.url / "x",
                    proxy=proxy.url,
                    proxy_auth=BasicAuth("user", "wrong"),
                )
                status = resp.status

    assert status == HTTPStatus.PROXY_AUTHENTICATION_REQUIRED
    target.assert_not_called("ok")


async def test_proxy_relays_redirect_verbatim() -> None:
    # The proxy must not follow redirects on the client's behalf — it relays
    # the target's response exactly.
    routes = [MockRoute("GET", "/x", "redir")]
    async with start_service(routes) as target:
        target.register(
            "redir",
            RawResponse(
                body=b"",
                status=HTTPStatus.FOUND,
                headers={"Location": "/elsewhere"},
            ),
        )
        async with start_proxy() as proxy:
            async with ClientSession() as s:
                resp = await s.get(
                    target.url / "x", proxy=proxy.url, allow_redirects=False
                )
                status = resp.status
                location = resp.headers.get("Location")

    assert status == HTTPStatus.FOUND
    assert location == "/elsewhere"
    proxy.assert_called(times=1)


async def test_proxy_preserves_multivalue_response_headers() -> None:
    # Duplicate response headers (e.g. several Set-Cookie) must survive the
    # forward — they must not collapse to a single value.
    async def target_handler(request: web.BaseRequest) -> web.Response:
        resp = web.Response(body=b"ok")
        resp.headers.add("X-Multi", "a")
        resp.headers.add("X-Multi", "b")
        return resp

    target = RawTestServer(target_handler)
    await target.start_server()
    try:
        async with start_proxy() as proxy:
            async with ClientSession() as s:
                resp = await s.get(f"http://127.0.0.1:{target.port}/x", proxy=proxy.url)
                values = resp.headers.getall("X-Multi")
    finally:
        await target.close()

    assert values == ["a", "b"]


async def test_proxy_assertions_helpers() -> None:
    async with start_proxy() as proxy:
        assert isinstance(proxy, MockProxyService)
        proxy.assert_not_called()
        with pytest.raises(AssertionError):
            proxy.last_call()
        with pytest.raises(AssertionError):
            proxy.assert_called(times=1)


async def test_proxy_assert_called_mismatch() -> None:
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy() as proxy:
            async with ClientSession() as s:
                await s.get(target.url / "x", proxy=proxy.url)

            assert proxy.last_call().request.method == "GET"
            with pytest.raises(AssertionError):
                proxy.assert_called(target="http://example.invalid/x")
            with pytest.raises(AssertionError):
                proxy.assert_called(method="POST")
            with pytest.raises(AssertionError):
                proxy.assert_called(times=2)
