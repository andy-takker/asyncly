from datetime import datetime
from uuid import uuid4

from prometheus_client import CollectorRegistry, generate_latest

from asyncly.srvmocker.models import MockService
from asyncly.srvmocker.responses.content import ContentResponse
from tests.plugins.instrumented_client import CatfactSchema, InstrumetedCatfactClient


async def test_prom_default_parse_pydantic_schema(
    instrumented_client_with_prometheus: InstrumetedCatfactClient,
) -> None:
    fact = await instrumented_client_with_prometheus.fetch_pydantic_cat_fact()
    assert fact == CatfactSchema(
        fact="test json",
        length=1,
        created_at=datetime(2025, 1, 1, 12, 15),
        colors=["red", "blue"],
    )


async def test_prom_check_metrics(
    instrumented_client_with_prometheus: InstrumetedCatfactClient,
    prometheus_registry: CollectorRegistry,
) -> None:
    await instrumented_client_with_prometheus.fetch_pydantic_cat_fact()

    data = generate_latest(prometheus_registry).decode()
    assert "http_client_requests_total" in data
    assert 'client="catfact"' in data
    assert 'method="GET"' in data
    assert 'route="/fact/json"' in data
    assert 'operation="get_pydantic_cat_fact"' in data
    assert 'status="200"' in data
    assert 'outcome="response"' in data
    assert "http_client_request_seconds_bucket" in data
    assert "http_client_in_flight" in data


async def test_prom_histogram_has_no_status_label(
    instrumented_client_with_prometheus: InstrumetedCatfactClient,
    prometheus_registry: CollectorRegistry,
) -> None:
    await instrumented_client_with_prometheus.fetch_pydantic_cat_fact()

    data = generate_latest(prometheus_registry).decode()
    bucket_lines = [
        line
        for line in data.splitlines()
        if line.startswith("http_client_request_seconds_bucket")
    ]
    assert bucket_lines
    # status must not multiply the histogram time series
    assert all("status=" not in line for line in bucket_lines)


async def test_prom_in_flight_returns_to_zero(
    instrumented_client_with_prometheus: InstrumetedCatfactClient,
    prometheus_registry: CollectorRegistry,
) -> None:
    await instrumented_client_with_prometheus.fetch_pydantic_cat_fact()

    data = generate_latest(prometheus_registry).decode()
    in_flight = [
        line for line in data.splitlines() if line.startswith("http_client_in_flight{")
    ]
    assert in_flight
    assert all(line.rsplit(" ", 1)[1] == "0.0" for line in in_flight)


async def test_prom_check_error_metrics(
    instrumented_client_with_prometheus: InstrumetedCatfactClient,
    prometheus_registry: CollectorRegistry,
    catfact_service: MockService,
) -> None:
    catfact_service.register("json_catfact", ContentResponse(status=500))
    try:
        await instrumented_client_with_prometheus.fetch_pydantic_cat_fact()
    except Exception:  # noqa: BLE001
        pass

    data = generate_latest(prometheus_registry).decode()
    assert "http_client_requests_total" in data
    assert "http_client_errors_total" in data
    assert 'client="catfact"' in data
    assert 'method="GET"' in data
    assert 'route="/fact/json"' in data
    assert 'status="500"' in data
    # a response arrived (500); the failure was in deserialization
    assert 'outcome="response"' in data
    assert "http_client_request_seconds_bucket" in data
    assert 'error_type="invalid_response"' in data


async def test_prom_disable_metrics(
    instrumented_client_with_prometheus: InstrumetedCatfactClient,
    prometheus_registry: CollectorRegistry,
) -> None:
    instrumented_client_with_prometheus.disable_metrics()

    fact = await instrumented_client_with_prometheus.fetch_pydantic_cat_fact()
    assert fact == CatfactSchema(
        fact="test json",
        length=1,
        created_at=datetime(2025, 1, 1, 12, 15),
        colors=["red", "blue"],
    )

    data = generate_latest(prometheus_registry).decode()

    assert 'client="catfact"' not in data
    assert 'method="GET"' not in data
    assert 'route="/fact/json"' not in data
    assert 'status="200"' not in data


async def test_prom_uuid_route_metrics(
    instrumented_client_with_prometheus: InstrumetedCatfactClient,
    prometheus_registry: CollectorRegistry,
) -> None:
    cat_id = uuid4()
    await instrumented_client_with_prometheus.fetch_cat_by_id(cat_id)

    data = generate_latest(prometheus_registry).decode()

    assert "http_client_requests_total" in data
    assert 'client="catfact"' in data
    assert 'method="GET"' in data
    assert 'route="/cats/:id"' in data
    # no explicit operation → operation falls back to the resolved route
    assert 'operation="/cats/:id"' in data
    assert 'status="200"' in data
    assert "http_client_request_seconds_bucket" in data
