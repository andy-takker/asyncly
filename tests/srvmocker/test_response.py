import asyncio
from datetime import datetime
from http import HTTPStatus

import pytest

from asyncly.client.handlers.exceptions import UnhandledStatusException
from asyncly.srvmocker.models import MockService
from asyncly.srvmocker.responses.content import ContentResponse
from asyncly.srvmocker.responses.json import JsonResponse
from asyncly.srvmocker.responses.sequence import SequenceResponse
from asyncly.srvmocker.responses.timeout import LatencyResponse
from tests.plugins.client import CatfactClient, CatfactSchema


@pytest.fixture
def content_response() -> ContentResponse:
    return ContentResponse(
        body=(
            '{"fact": "test", "length": 4, "created_at":'
            '"2025-01-01T12:15:00.000000", "colors": ["red", "blue"]}'
        ),
        headers={"Content-Type": "application/json"},
    )


@pytest.fixture
def json_response() -> JsonResponse:
    return JsonResponse(
        {
            "fact": "another fact",
            "length": 12,
            "created_at": "2025-01-01T12:15:00.000000",
            "colors": ["red", "blue"],
        }
    )


@pytest.fixture
def sequence_response(
    json_response: JsonResponse, content_response: ContentResponse
) -> SequenceResponse:
    return SequenceResponse([json_response, content_response])


async def test_content_response(
    catfact_client: CatfactClient,
) -> None:
    fact = await catfact_client.fetch_json_cat_fact()
    assert fact == "test json"


async def test_latency_response__timeout(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    content_response: ContentResponse,
) -> None:
    catfact_service.register(
        "json_catfact", LatencyResponse(content_response, latency=1)
    )

    with pytest.raises(asyncio.TimeoutError):
        await catfact_client.fetch_json_cat_fact(timeout=0.5)


async def test_latency_response__ok(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    content_response: ContentResponse,
) -> None:
    catfact_service.register(
        "json_catfact", LatencyResponse(content_response, latency=0)
    )
    assert await catfact_client.fetch_json_cat_fact(timeout=0.5) == "test"


async def test_json_response(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    json_response: JsonResponse,
) -> None:
    catfact_service.register("json_catfact", json_response)
    fact = await catfact_client.fetch_pydantic_cat_fact()
    assert fact == CatfactSchema(
        fact="another fact",
        length=12,
        created_at=datetime(2025, 1, 1, 12, 15),
        colors=["red", "blue"],
    )


async def test_sequence_response(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    sequence_response: SequenceResponse,
) -> None:
    catfact_service.register("json_catfact", sequence_response)
    first = await catfact_client.fetch_json_cat_fact()
    second = await catfact_client.fetch_json_cat_fact()
    assert [first, second] == ["another fact", "test"]


async def test_unhandled_status_exception(
    catfact_client: CatfactClient,
    catfact_service: MockService,
) -> None:
    catfact_service.register(
        "json_catfact",
        ContentResponse(
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        ),
    )
    with pytest.raises(UnhandledStatusException):
        await catfact_client.fetch_json_cat_fact()
