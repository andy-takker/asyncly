# HTTP client

[`BaseHttpClient`][asyncly.BaseHttpClient] is a thin, typed base class for
building API clients on top of an aiohttp `ClientSession`. You subclass it and
add one method per endpoint.

## Anatomy

```python
from http import HTTPStatus
from types import MappingProxyType

from aiohttp import hdrs
from asyncly import BaseHttpClient, DEFAULT_TIMEOUT, ResponseHandlersType
from asyncly.client.handlers.pydantic import parse_model
from asyncly.client.timeout import TimeoutType


class CatfactClient(BaseHttpClient):
    FACT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {HTTPStatus.OK: parse_model(CatFact)}
    )

    async def fetch_fact(self, timeout: TimeoutType = DEFAULT_TIMEOUT) -> CatFact:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact",
            handlers=self.FACT_HANDLERS,
            timeout=timeout,
        )
```

Key ideas:

- The **session is injected** — you create and own the `ClientSession`, the
  client just uses it. This keeps connection pooling, auth, and lifecycle in
  your control.
- `self._url` is the base URL as a [`yarl.URL`](https://yarl.aio-libs.org/); build
  endpoint URLs with the `/` operator.
- `self._make_req(...)` issues the request and dispatches the response to a
  [handler](response-handlers.md) chosen by status code.

## Construction

```python
from aiohttp import ClientSession

async with ClientSession() as session:
    client = CatfactClient(
        url="https://catfact.ninja",   # str or yarl.URL
        session=session,
        client_name="catfact",         # used in metrics and error messages
    )
```

The `url` property exposes the configured base URL:

```python
client.url  # URL('https://catfact.ninja')
```

## Timeouts

Every request method takes a `timeout` of type
[`TimeoutType`][asyncly.TimeoutType] — an `aiohttp.ClientTimeout`, a
`datetime.timedelta`, or a plain number of seconds. They are all normalized
internally:

```python
from datetime import timedelta

await client.fetch_fact(timeout=2)                    # 2 seconds
await client.fetch_fact(timeout=2.5)                  # 2.5 seconds
await client.fetch_fact(timeout=timedelta(seconds=2)) # timedelta
```

The default is aiohttp's `DEFAULT_TIMEOUT`, re-exported from the top-level
`asyncly` package.

## Proxy support

`BaseHttpClient` accepts `proxy` and `proxy_auth`, set once on the client or
overridden per request. They are forwarded to aiohttp:

```python
from aiohttp import BasicAuth

client = CatfactClient(
    url="https://catfact.ninja",
    session=session,
    client_name="catfact",
    proxy="http://127.0.0.1:8080",
    proxy_auth=BasicAuth("user", "secret"),
)
```

See [Proxy testing](proxy-testing.md) for spinning up a mock proxy to verify a
client really routes through one.

## Extra request arguments

`_make_req` forwards any extra keyword arguments to
`ClientSession.request`, so you can pass `headers`, `params`, `json`, `data`,
etc.:

```python
return await self._make_req(
    method=hdrs.METH_POST,
    url=self._url / "items",
    handlers=self.CREATE_HANDLERS,
    json={"name": name},
    headers={"X-Tenant": tenant},
)
```

## Error handling

If a response status has no matching handler, `_make_req` raises
[`UnhandledStatusException`][asyncly.client.handlers.exceptions.UnhandledStatusException],
which carries the `status`, `url`, and `client_name`. Map the statuses you
expect — including error codes — to handlers. See
[Response handlers](response-handlers.md#handling-errors).

## Metrics

To record request metrics (latency, status, errors), use
[`InstrumentableHttpClient`](instrumentation.md) instead, which adds
`enable_metrics()` / `instrument()` on top of the same API.
