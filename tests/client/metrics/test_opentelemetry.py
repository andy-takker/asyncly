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
        and attrs.get("status") == "200"
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
        and attrs.get("status") == "200"
        and h["count"] is not None
        and h["sum"] is not None
    ]
    assert matches


async def test_otel_error_handled(
    instrumented_client_with_opentelemetry: InstrumetedCatfactClient,
    otel_reader: InMemoryMetricReader,
    catfact_service: MockService,
) -> None:
    catfact_service.register("json_catfact", ContentResponse(status=500))
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
        and attrs.get("error_type") == "ValidationError"
    ]
    assert matches
