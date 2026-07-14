from collections.abc import AsyncIterator

import pytest
from aiohttp import ClientSession, TCPConnector
from prometheus_client import CollectorRegistry, generate_latest
from yarl import URL

from asyncly.client.metrics.sinks.prometheus import (
    PrometheusPoolCollector,
    PrometheusSink,
)
from asyncly.client.metrics.trace_config import build_trace_config
from tests.plugins.instrumented_client import InstrumetedCatfactClient


@pytest.fixture
def traced_registry() -> CollectorRegistry:
    return CollectorRegistry()


@pytest.fixture
def traced_sink(traced_registry: CollectorRegistry) -> PrometheusSink:
    return PrometheusSink(registry=traced_registry)


@pytest.fixture
async def traced_client(
    catfact_url: URL,
    traced_sink: PrometheusSink,
) -> AsyncIterator[InstrumetedCatfactClient]:
    connector = TCPConnector(limit=5)
    async with ClientSession(
        connector=connector,
        trace_configs=[build_trace_config(traced_sink)],
    ) as session:
        client = InstrumetedCatfactClient(
            client_name="catfact",
            session=session,
            url=catfact_url,
        )
        client.enable_metrics(traced_sink)
        yield client


async def test_phase_metrics_recorded_on_fresh_connection(
    traced_client: InstrumetedCatfactClient,
    traced_registry: CollectorRegistry,
) -> None:
    await traced_client.fetch_pydantic_cat_fact()

    data = generate_latest(traced_registry).decode()
    assert "http_client_phase_duration_seconds_bucket" in data
    # a fresh connection resolves DNS and connects
    assert 'phase="connect"' in data
    assert 'operation="get_pydantic_cat_fact"' in data
    # ttfb / body_read observed on the response
    assert 'phase="ttfb"' in data


async def test_reused_connection_skips_connect_phase(
    traced_client: InstrumetedCatfactClient,
    traced_registry: CollectorRegistry,
) -> None:
    # first request establishes the connection
    await traced_client.fetch_json_cat_fact()
    # second request reuses it — no new connect sample
    await traced_client.fetch_json_cat_fact()

    data = generate_latest(traced_registry).decode()
    connect_count = [
        line
        for line in data.splitlines()
        if line.startswith("http_client_phase_duration_seconds_count")
        and 'phase="connect"' in line
    ]
    # exactly one connect observation despite two requests
    assert connect_count
    assert all(line.rsplit(" ", 1)[1] == "1.0" for line in connect_count)


async def test_pool_collector_reports_state(
    catfact_url: URL,
    traced_registry: CollectorRegistry,
) -> None:
    connector = TCPConnector(limit=5)
    collector = PrometheusPoolCollector(upstream="catfact")
    collector.bind(connector)
    traced_registry.register(collector)

    async with ClientSession(connector=connector) as session:
        client = InstrumetedCatfactClient(
            client_name="catfact",
            session=session,
            url=catfact_url,
        )
        await client.fetch_json_cat_fact()

        data = generate_latest(traced_registry).decode()
        assert 'http_client_pool_connections{state="idle",upstream="catfact"}' in data
        assert 'http_client_pool_connections{state="active",upstream="catfact"}' in data


def test_build_trace_config_inert_for_sink_without_phases() -> None:
    class LifecycleLessSink:
        def observe_request(self, **kwargs: object) -> None:
            return

    tc = build_trace_config(LifecycleLessSink())  # type: ignore[arg-type]
    # no phase callbacks registered
    assert tc.on_connection_create_start == []
