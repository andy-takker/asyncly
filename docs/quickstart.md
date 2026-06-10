# Quickstart

This walkthrough builds a small HTTP client and tests it against a real mock
server — no network, no monkeypatching. It mirrors the runnable example in
[`examples/`](https://github.com/andy-takker/asyncly/tree/master/examples).

Install asyncly with the Pydantic extra:

```bash
pip install "asyncly[pydantic]"
```

## 1. Define a client

Subclass [`BaseHttpClient`][asyncly.BaseHttpClient] and map status codes to
[response handlers](guide/response-handlers.md). Here `parse_model` decodes a
`200 OK` body into a Pydantic model:

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

You own the `ClientSession`; the client just wraps it:

```python
async def main() -> None:
    async with ClientSession() as session:
        client = CatfactClient(
            url="https://catfact.ninja",
            session=session,
            client_name="catfact",
        )
        print(await client.fetch_fact())
```

## 2. Test it against a real mock server

[`start_service`][asyncly.srvmocker.start_service] starts an `aiohttp.TestServer`,
returns a [`MockService`][asyncly.srvmocker.MockService], and gives you a URL to
point the client at. Register responses, run the client, and assert what it sent:

```python
from asyncly.srvmocker import JsonResponse, MockRoute, start_service


async def test_fetch_fact() -> None:
    routes = [MockRoute("GET", "/fact", "fact")]
    async with start_service(routes) as service:
        service.register(
            "fact",
            JsonResponse({"fact": "Cats sleep a lot.", "length": 17}),
        )

        async with ClientSession() as session:
            client = CatfactClient(
                url=service.url, session=session, client_name="catfact"
            )
            fact = await client.fetch_fact()

        assert fact == CatFact(fact="Cats sleep a lot.", length=17)
        service.assert_called("fact", times=1)
```

## 3. Use the pytest plugin (less boilerplate)

asyncly ships a [pytest plugin](guide/pytest-plugin.md). Override `mock_routes`
to declare your API surface and use the `mock_service` fixture:

```python
import pytest
from aiohttp import ClientSession

from asyncly.srvmocker import JsonResponse, MockRoute


@pytest.fixture
def mock_routes():
    return [MockRoute("GET", "/fact", "fact")]


async def test_with_plugin(mock_service) -> None:
    mock_service.register("fact", JsonResponse({"fact": "Meow.", "length": 5}))

    async with ClientSession() as session:
        client = CatfactClient(
            url=mock_service.url, session=session, client_name="catfact"
        )
        assert (await client.fetch_fact()).length == 5
```

## Where to next

- [HTTP client](guide/http-client.md) — timeouts, proxies, error handling.
- [Response handlers](guide/response-handlers.md) — JSON, Pydantic, msgspec.
- [Mock server](guide/mock-server.md) — dynamic responses and assertions.
- [Request matching](guide/request-matching.md) — branch on body/headers/query.
