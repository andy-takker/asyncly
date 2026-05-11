import asyncio
from datetime import datetime
from http import HTTPStatus

import pytest
from aiohttp.test_utils import make_mocked_request

from asyncly.client.handlers.exceptions import UnhandledStatusException
from asyncly.srvmocker.exceptions import SequenceExhausted
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
        "json_catfact", LatencyResponse(content_response, latency=0.5)
    )

    with pytest.raises(asyncio.TimeoutError):
        await catfact_client.fetch_json_cat_fact(timeout=0.1)


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


async def test_sequence_response__raises_sequence_exhausted_on_exhaustion(
    json_response: JsonResponse,
) -> None:
    # Unit test: exhaustion happens inside an aiohttp request handler, where
    # aiohttp wraps any non-HTTPException into a 500. From the client side
    # you'd see UnhandledStatusException, not SequenceExhausted. To assert
    # the typed exception, drive .response() directly with a mocked request.
    seq = SequenceResponse([json_response])
    req = make_mocked_request("GET", "/")
    await seq.response(req)
    with pytest.raises(SequenceExhausted):
        await seq.response(req)


async def test_sequence_response__cycles_when_configured(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    json_response: JsonResponse,
    content_response: ContentResponse,
) -> None:
    catfact_service.register(
        "json_catfact",
        SequenceResponse([json_response, content_response], on_exhausted="cycle"),
    )
    a = await catfact_client.fetch_json_cat_fact()
    b = await catfact_client.fetch_json_cat_fact()
    c = await catfact_client.fetch_json_cat_fact()
    assert [a, b, c] == ["another fact", "test", "another fact"]


async def test_sequence_response__returns_last_when_configured(
    catfact_client: CatfactClient,
    catfact_service: MockService,
    json_response: JsonResponse,
    content_response: ContentResponse,
) -> None:
    catfact_service.register(
        "json_catfact",
        SequenceResponse([json_response, content_response], on_exhausted="last"),
    )
    await catfact_client.fetch_json_cat_fact()
    await catfact_client.fetch_json_cat_fact()
    repeat = await catfact_client.fetch_json_cat_fact()
    assert repeat == "test"


async def test_sequence_response__empty_raises_value_error() -> None:
    with pytest.raises(ValueError):
        SequenceResponse([])
