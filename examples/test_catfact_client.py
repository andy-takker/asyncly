import asyncio
from collections.abc import AsyncIterator
from http import HTTPStatus
from types import MappingProxyType

import pytest
from aiohttp import ClientSession, hdrs
from pydantic import BaseModel
from yarl import URL

from asyncly import DEFAULT_TIMEOUT, BaseHttpClient, ResponseHandlersType
from asyncly.client.handlers.pydantic import parse_model
from asyncly.client.timeout import TimeoutType
from asyncly.srvmocker.models import MockRoute, MockService
from asyncly.srvmocker.responses import JsonResponse, LatencyResponse
from asyncly.srvmocker.service import start_service


class CatfactSchema(BaseModel):
    fact: str
    length: int


class CatfactClient(BaseHttpClient):
    RANDOM_CATFACT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_model(CatfactSchema),
        }
    )

    async def fetch_random_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactSchema:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact",
            handlers=self.RANDOM_CATFACT_HANDLERS,
            timeout=timeout,
        )


@pytest.fixture
async def catafact_service() -> AsyncIterator[MockService]:
    routes = [
        MockRoute("GET", "/fact", "random_catfact"),
    ]
    async with start_service(routes) as service:
        service.register(
            "random_catfact",
            JsonResponse({"fact": "test", "length": 4}),
        )
        yield service


@pytest.fixture
def catfact_url(catafact_service: MockService) -> URL:
    return catafact_service.url


@pytest.fixture
async def catfact_client(catfact_url: URL) -> AsyncIterator[CatfactClient]:
    async with ClientSession() as session:
        client = CatfactClient(
            client_name="catfact",
            session=session,
            url=catfact_url,
        )
        yield client


async def test_fetch_random_catfact(catfact_client: CatfactClient) -> None:
    # use default registered handler
    fact = await catfact_client.fetch_random_cat_fact()
    assert fact == CatfactSchema(fact="test", length=4)


async def test_fetch_random_catfact_timeout(
    catfact_client: CatfactClient,
    catafact_service: MockService,
) -> None:
    # change default registered handler to time error handler
    catafact_service.register(
        "random_catfact",
        LatencyResponse(
            wrapped=JsonResponse({"fact": "test", "length": 4}),
            latency=1.5,
        ),
    )
    with pytest.raises(asyncio.TimeoutError):
        await catfact_client.fetch_random_cat_fact(timeout=1)
