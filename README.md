# Asyncly

[![PyPI version](https://img.shields.io/pypi/v/asyncly.svg)](https://pypi.org/project/asyncly/)
[![Python versions](https://img.shields.io/pypi/pyversions/asyncly.svg)](https://pypi.org/project/asyncly/)
[![License](https://img.shields.io/pypi/l/asyncly.svg)](https://pypi.org/project/asyncly/)
[![Documentation](https://img.shields.io/badge/docs-mkdocs--material-blue.svg)](https://andy-takker.github.io/asyncly/)

**A tiny async HTTP client and a *real* aiohttp mock server for testing your integrations — built on [aiohttp](https://docs.aiohttp.org/).**

asyncly gives you two pieces that fit together:

- **`BaseHttpClient`** — a thin, typed base class for HTTP clients with per-status
  response handlers, flexible timeouts, and first-class proxy support.
- **`srvmocker`** — spin up a *real* aiohttp test server (not a transport patch)
  to simulate upstreams in tests, assert what your client sent, and even route
  through a mock proxy.

📖 **[Read the full documentation →](https://andy-takker.github.io/asyncly/)**

## Installation

```bash
pip install asyncly
```

Optional extras — `msgspec`, `pydantic`, `orjson`, `prometheus`, `opentelemetry`:

```bash
pip install "asyncly[pydantic]"
```

## Quickstart

Define a client by subclassing `BaseHttpClient` and mapping status codes to handlers:

```python
from http import HTTPStatus
from types import MappingProxyType

from aiohttp import ClientSession, hdrs
from pydantic import BaseModel

from asyncly import BaseHttpClient, DEFAULT_TIMEOUT, ResponseHandlersType
from asyncly.client.handlers.pydantic import parse_model
from asyncly.client.timeout import TimeoutType


class CatFact(BaseModel):
    fact: str
    length: int


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

Test it against a real mock server — no network, no monkeypatching:

```python
from asyncly.srvmocker import JsonResponse, MockRoute, start_service


async def test_fetch_fact() -> None:
    routes = [MockRoute("GET", "/fact", "fact")]
    async with start_service(routes) as service:
        service.register("fact", JsonResponse({"fact": "Cats sleep a lot.", "length": 17}))

        async with ClientSession() as session:
            client = CatfactClient(url=service.url, session=session, client_name="catfact")
            fact = await client.fetch_fact()

        assert fact.fact == "Cats sleep a lot."
        service.assert_called("fact", times=1)
```

Prefer fixtures over boilerplate? asyncly ships a pytest plugin with `mock_service`
and `mock_proxy`. See the [Quickstart](https://andy-takker.github.io/asyncly/) for more.

## Why asyncly?

Unlike transport-patching mocks (`aioresponses`, `respx`), `srvmocker` runs a real
`aiohttp.TestServer` inside your test loop — catching real sockets, timeouts, header
auto-injection, and serialization quirks. See
[Testing strategies](https://andy-takker.github.io/asyncly/) for the full comparison.

## License

[MIT](https://github.com/andy-takker/asyncly/blob/master/LICENSE)
