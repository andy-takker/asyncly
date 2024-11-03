import asyncio

import pytest

from asyncly.srvmocker.models import MockService
from asyncly.srvmocker.responses import (
    ContentResponse,
    JsonResponse,
    LatencyResponse,
    MockSeqResponse,
)
from tests.plugins.client import CatfactClient, CatfactSchema


@pytest.fixture
def content_response() -> ContentResponse:
    return ContentResponse(
        body='{"fact": "test", "length": 4}',
        headers={"Content-Type": "application/json"},
    )


@pytest.fixture
def json_response() -> JsonResponse:
    return JsonResponse({"fact": "another fact", "length": 12})


@pytest.fixture
def sequence_response(
    json_response: JsonResponse, content_response: ContentResponse
) -> MockSeqResponse:
    return MockSeqResponse([json_response, content_response])


async def test_content_response(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    content_response: ContentResponse,
) -> None:
    catfact_service.register("random_catfact", content_response)
    fact = await catfact_client.fetch_json_cat_fact()
    assert fact == "test"


async def test_latency_response(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    content_response: ContentResponse,
) -> None:
    catfact_service.register(
        "random_catfact", LatencyResponse(content_response, latency=2.5)
    )

    with pytest.raises(asyncio.TimeoutError):
        await catfact_client.fetch_json_cat_fact(timeout=0.5)


async def test_json_response(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    json_response: JsonResponse,
) -> None:
    catfact_service.register("random_catfact", json_response)
    fact = await catfact_client.fetch_pydantic_cat_fact()
    assert fact == CatfactSchema(fact="another fact", length=12)


async def test_mock_seq_response(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    sequence_response: MockSeqResponse,
) -> None:
    catfact_service.register("random_catfact", sequence_response)
    first = await catfact_client.fetch_json_cat_fact()
    second = await catfact_client.fetch_json_cat_fact()
    assert [first, second] == ["another fact", "test"]
