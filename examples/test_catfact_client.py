import asyncio
from collections.abc import AsyncIterator

import pytest
from aiohttp import ClientSession
from yarl import URL

from asyncly.srvmocker.models import MockRoute, MockService
from asyncly.srvmocker.responses.json import JsonResponse
from asyncly.srvmocker.responses.msgpack import MsgpackResponse
from asyncly.srvmocker.responses.timeout import LatencyResponse
from asyncly.srvmocker.service import start_service
from examples.catfact_client import CatfactClient, CatfactModel, CatfactStruct


async def test_fetch_catfact_model(catfact_client: CatfactClient) -> None:
    # use default registered handler
    fact = await catfact_client.fetch_catfact_model()
    assert fact == CatfactModel(fact="test json", length=9)


async def test_fetch_catfact_model_with_timeout(
    catfact_client: CatfactClient,
    catfact_service: MockService,
) -> None:
    # change default registered handler to time error handler
    catfact_service.register(
        "json_catfact",
        LatencyResponse(
            wrapped=JsonResponse({"fact": "slow json", "length": 9}),
            latency=0.5,
        ),
    )
    with pytest.raises(asyncio.TimeoutError):
        await catfact_client.fetch_catfact_model(timeout=0.1)


async def test_fetch_catfact_msgpack(
    catfact_client: CatfactClient,
    catfact_service: MockService,
) -> None:
    catfact_service.register(
        "msgpack_catfact",
        MsgpackResponse(
            {
                "fact": "test msgpack",
                "length": 9,
            },
        ),
    )
    fact = await catfact_client.fetch_catfact_msgpack()
    assert fact == CatfactStruct(fact="test msgpack", length=9)


@pytest.fixture
async def catfact_service() -> AsyncIterator[MockService]:
    routes = [
        MockRoute("GET", "/fact/json", "json_catfact"),
        MockRoute("GET", "/fact/msgpack", "msgpack_catfact"),
    ]
    async with start_service(routes) as service:
        service.register(
            "json_catfact",
            JsonResponse(
                {
                    "fact": "test json",
                    "length": 9,
                },
            ),
        )

        yield service


@pytest.fixture
def catfact_url(catfact_service: MockService) -> URL:
    return catfact_service.url


@pytest.fixture
async def catfact_client(catfact_url: URL) -> AsyncIterator[CatfactClient]:
    async with ClientSession() as session:
        client = CatfactClient(
            client_name="catfact",
            session=session,
            url=catfact_url,
        )
        yield client
