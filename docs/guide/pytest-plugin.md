# Pytest plugin

asyncly ships a pytest plugin, auto-registered via an entry point — there is
nothing to add to `conftest.py`. It removes the boilerplate of wiring
[`start_service`](mock-server.md) into every test module.

## Fixtures

| Fixture | Yields | Purpose |
| --- | --- | --- |
| `mock_routes` | `Iterable[MockRoute]` | Override to declare your server's routes |
| `mock_service` | [`MockService`][asyncly.srvmocker.MockService] | A started mock server (uses `mock_routes`) |
| `mock_proxy` | [`MockProxyService`][asyncly.srvmocker.MockProxyService] | A forwarding [mock proxy](proxy-testing.md) |

## Usage

Override `mock_routes` to declare the API surface, then use `mock_service`:

```python
import pytest
from aiohttp import ClientSession

from asyncly.srvmocker import JsonResponse, MockRoute


@pytest.fixture
def mock_routes():
    return [MockRoute("GET", "/fact", "fact")]


async def test_fetch_fact(mock_service) -> None:
    mock_service.register("fact", JsonResponse({"fact": "Meow.", "length": 5}))

    async with ClientSession() as session:
        client = CatfactClient(
            url=mock_service.url, session=session, client_name="catfact"
        )
        fact = await client.fetch_fact()

    assert fact.length == 5
    mock_service.assert_called("fact", times=1)
```

The `mock_service` fixture is automatically started before the test and closed
after it.

## Building your own fixtures

The plugin's fixtures are deliberately small. When you need finer control —
sharing a client across tests, custom server lifetime, TLS — wire `start_service`
yourself:

```python
from collections.abc import AsyncIterator

import pytest
from aiohttp import ClientSession

from asyncly.srvmocker import JsonResponse, MockRoute, MockService, start_service


@pytest.fixture
async def catfact_service() -> AsyncIterator[MockService]:
    routes = [MockRoute("GET", "/fact", "fact")]
    async with start_service(routes) as service:
        service.register("fact", JsonResponse({"fact": "test", "length": 4}))
        yield service


@pytest.fixture
async def catfact_client(catfact_service: MockService) -> AsyncIterator[CatfactClient]:
    async with ClientSession() as session:
        yield CatfactClient(
            url=catfact_service.url, session=session, client_name="catfact"
        )
```
