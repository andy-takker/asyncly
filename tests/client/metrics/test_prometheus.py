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
    assert "asyncly_client_requests_total" in data
    assert 'client="catfact"' in data
    assert 'method="GET"' in data
    assert 'route="/fact/json"' in data
    assert 'status="200"' in data
    assert "asyncly_client_request_seconds_bucket" in data


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
    assert "asyncly_client_requests_total" in data
    assert "asyncly_client_errors_total" in data
    assert 'client="catfact"' in data
    assert 'method="GET"' in data
    assert 'route="/fact/json"' in data
    assert 'status="500"' in data
    assert "asyncly_client_request_seconds_bucket" in data
    assert 'error_type="ValidationError"' in data


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

    assert "asyncly_client_requests_total" in data
    assert "asyncly_client_errors_total" in data
    assert 'client="catfact"' in data
    assert 'method="GET"' in data
    assert 'route="/cats/:id"' in data
    assert 'status="200"' in data
    assert "asyncly_client_request_seconds_bucket" in data
