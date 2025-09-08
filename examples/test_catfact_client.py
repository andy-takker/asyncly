import asyncio

import pytest

from asyncly.srvmocker.models import MockService
from asyncly.srvmocker.responses.json import JsonResponse
from asyncly.srvmocker.responses.timeout import LatencyResponse
from tests.plugins.client import CatfactClient, CatfactSchema


async def test_fetch_random_catfact(catfact_client: CatfactClient) -> None:
    # use default registered handler
    fact = await catfact_client.fetch_json_cat_fact()
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
        await catfact_client.fetch_json_cat_fact(timeout=1)
