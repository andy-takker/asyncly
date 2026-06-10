# Mock server

[`start_service`][asyncly.srvmocker.start_service] starts a **real**
`aiohttp.TestServer` and yields a [`MockService`][asyncly.srvmocker.MockService]
you control. Point your client at `service.url` and the requests hit a genuine
server in your test loop.

```python
from asyncly.srvmocker import JsonResponse, MockRoute, start_service


async def test_fetch_fact() -> None:
    routes = [MockRoute("GET", "/fact", "fact")]
    async with start_service(routes) as service:
        service.register("fact", JsonResponse({"fact": "Meow.", "length": 5}))
        # ... point your client at service.url and call it
        service.assert_called("fact", times=1)
```

## Declaring routes

A [`MockRoute`][asyncly.srvmocker.MockRoute] binds an HTTP method and path to a
**handler name** — a label you register a response under:

```python
MockRoute(method="GET", path="/fact", handler_name="fact")
```

Multiple routes can share the same `(method, path)` and be distinguished by a
[`Match`](request-matching.md). Declare the full set of routes up front when
calling `start_service`.

## Registering responses

Register a response under a handler name with `register`. You can register
before any request and **re-register** mid-test to change behavior:

```python
service.register("fact", JsonResponse({"fact": "Meow.", "length": 5}))

# later in the test, swap the response
service.register("fact", JsonResponse({"fact": "Purr.", "length": 5}))
```

See [Responses & serializers](responses.md) for the full catalog
(`JsonResponse`, `RawResponse`, `SequenceResponse`, `LatencyResponse`,
msgpack/TOML/YAML, and more).

## Asserting what your client sent

`MockService` records every request. Read the history to assert your client
behaved correctly:

```python
service.assert_called(
    "create",
    json={"name": "Whiskers"},
    headers={"Content-Type": "application/json"},
)
assert service.last_call("create").body == b'{"name": "Whiskers"}'
```

Available helpers:

| Method | Purpose |
| --- | --- |
| `get_calls(name)` | All recorded calls for a handler, as `list[RequestHistory]` |
| `last_call(name)` | The most recent call (raises `AssertionError` if none) |
| `assert_called(name, *, times=, json=, body=, headers=, query=)` | Assert a matching call happened |
| `assert_not_called(name)` | Assert the handler received no requests |

`assert_called` matches a **subset**: `headers` and `query` need only contain the
keys you list; `json` and `body` must match exactly.

## HTTPS / TLS

Pass an `ssl.SSLContext` to serve over HTTPS — `service.url` then reports
`scheme="https"`:

```python
import ssl
from asyncly.srvmocker import start_service

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain("cert.pem", "key.pem")

async with start_service(routes, ssl_context=ctx) as service:
    assert service.url.scheme == "https"
```

On the client side, build a `TCPConnector` with a matching client SSL context.

## Less boilerplate

The [pytest plugin](pytest-plugin.md) wires `start_service` into a `mock_service`
fixture so you don't repeat this setup in every test module.
