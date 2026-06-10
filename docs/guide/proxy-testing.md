# Proxy testing

asyncly has two sides to proxy support:

- On the **client**, [`BaseHttpClient`](http-client.md#proxy-support) accepts
  `proxy` / `proxy_auth`.
- On the **server**, [`start_proxy`][asyncly.srvmocker.start_proxy] spins up an
  in-process forwarding HTTP proxy so you can verify a client genuinely routes
  through one.

!!! note
    Only plain HTTP targets are supported (no `CONNECT` / HTTPS tunnelling).

## The mock proxy

`start_proxy` records every request that passes through it and forwards it to
the real target — typically another [`start_service`](mock-server.md). It yields
a [`MockProxyService`][asyncly.srvmocker.MockProxyService]:

```python
from aiohttp import ClientSession
from asyncly.srvmocker import JsonResponse, MockRoute, start_proxy, start_service


async def test_routes_through_proxy() -> None:
    routes = [MockRoute("GET", "/fact", "fact")]
    async with start_service(routes) as target:
        target.register("fact", JsonResponse({"fact": "ok"}))
        async with start_proxy() as proxy:
            async with ClientSession() as session:
                resp = await session.get(target.url / "fact", proxy=proxy.url)
                assert (await resp.json()) == {"fact": "ok"}

        proxy.assert_called(times=1, method="GET")
```

Responses are relayed **verbatim** — the proxy does not follow redirects,
decompress bodies, or collapse duplicate headers.

## Proxy authentication

Pass `auth` to require a `Proxy-Authorization` header. Requests that are missing
it or send the wrong credentials get a `407 Proxy Authentication Required` and
are **not** forwarded:

```python
from aiohttp import BasicAuth

async with start_proxy(auth=BasicAuth("user", "secret")) as proxy:
    async with ClientSession() as session:
        resp = await session.get(
            target.url / "fact",
            proxy=proxy.url,
            proxy_auth=BasicAuth("user", "secret"),
        )
    proxy.assert_called(headers={"Proxy-Authorization": BasicAuth("user", "secret").encode()})
```

## Assertions

`MockProxyService` mirrors [`MockService`](mock-server.md#asserting-what-your-client-sent)'s
helpers, reading from the history of forwarded requests:

- `get_calls() -> list[RequestHistory]`
- `last_call() -> RequestHistory`
- `assert_called(*, times=, target=, method=, json=, body=, headers=, query=)`
- `assert_not_called()`

The extra `target` predicate matches the absolute destination URL the client
asked the proxy to reach.

## Pytest fixture

The [pytest plugin](pytest-plugin.md) exposes a ready-to-use `mock_proxy`
fixture:

```python
async def test_with_fixture(mock_proxy, mock_service) -> None:
    mock_service.register("fact", JsonResponse({"fact": "ok"}))
    async with ClientSession() as session:
        await session.get(mock_service.url / "fact", proxy=mock_proxy.url)
    mock_proxy.assert_called(times=1)
```
