from http import HTTPStatus

from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from asyncly.srvmocker.models import MockService
from asyncly.srvmocker.responses.content import ContentResponse
from tests.plugins.instrumented_client import InstrumetedCatfactClient
from tests.plugins.opentelemetry import collect_points


async def test_otel_success_handled_request_requests_counter(
    instrumented_client_with_opentelemetry: InstrumetedCatfactClient,
    otel_reader: InMemoryMetricReader,
) -> None:
    await instrumented_client_with_opentelemetry.fetch_pydantic_cat_fact()
    points = collect_points(otel_reader)

    req_points = points.get("http_client_requests_total", [])
    matches = [
        (attrs, v)
        for (attrs, v) in req_points
        if attrs.get("client") == "catfact"
        and attrs.get("method") == "GET"
        and attrs.get("route") == "/fact/json"
        and attrs.get("operation") == "get_pydantic_cat_fact"
        and attrs.get("status") == "200"
        and attrs.get("outcome") == "response"
    ]
    assert matches


async def test_otel_success_handled_request_hist(
    instrumented_client_with_opentelemetry: InstrumetedCatfactClient,
    otel_reader: InMemoryMetricReader,
) -> None:
    await instrumented_client_with_opentelemetry.fetch_pydantic_cat_fact()

    points = collect_points(otel_reader)
    hist_points = points.get("http_client_request_seconds", [])
    matches = [
        (attrs, h)
        for (attrs, h) in hist_points
        if attrs.get("client") == "catfact"
        and attrs.get("method") == "GET"
        and attrs.get("route") == "/fact/json"
        and attrs.get("outcome") == "response"
        and "status" not in attrs
        and h["count"] is not None
        and h["sum"] is not None
    ]
    assert matches


async def test_otel_in_flight_counter(
    instrumented_client_with_opentelemetry: InstrumetedCatfactClient,
    otel_reader: InMemoryMetricReader,
) -> None:
    await instrumented_client_with_opentelemetry.fetch_pydantic_cat_fact()

    points = collect_points(otel_reader)
    in_flight = points.get("http_client_in_flight", [])
    # up-down counter nets to zero once the request completes
    assert in_flight
    assert all(v == 0 for (_attrs, v) in in_flight)


async def test_otel_error_handled(
    instrumented_client_with_opentelemetry: InstrumetedCatfactClient,
    otel_reader: InMemoryMetricReader,
    catfact_service: MockService,
) -> None:
    catfact_service.register(
        "json_catfact",
        ContentResponse(status=HTTPStatus.INTERNAL_SERVER_ERROR),
    )
    try:
        await instrumented_client_with_opentelemetry.fetch_pydantic_cat_fact()
    except Exception:  # noqa: BLE001
        pass

    points = collect_points(otel_reader)
    req_points = points.get("http_client_requests_total", [])
    matches = [
        (attrs, v)
        for (attrs, v) in req_points
        if attrs.get("client") == "catfact"
        and attrs.get("method") == "GET"
        and attrs.get("route") == "/fact/json"
        and attrs.get("status") == "500"
    ]
    assert matches

    error_points = points.get("http_client_errors_total", [])
    matches = [
        (attrs, v)
        for (attrs, v) in error_points
        if attrs.get("client") == "catfact"
        and attrs.get("method") == "GET"
        and attrs.get("route") == "/fact/json"
        and attrs.get("error_type") == "invalid_response"
    ]
    assert matches
