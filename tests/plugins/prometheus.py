from collections.abc import Generator

import pytest
from prometheus_client import CollectorRegistry

from asyncly.client.metrics.instrumentable_client import InstrumentableHttpClient
from asyncly.client.metrics.sinks.prometheus import PrometheusSink
from tests.plugins.instrumented_client import InstrumetedCatfactClient


@pytest.fixture
def prometheus_registry() -> CollectorRegistry:
    return CollectorRegistry()


@pytest.fixture
def prometheus_sink(prometheus_registry: CollectorRegistry) -> PrometheusSink:
    return PrometheusSink(registry=prometheus_registry)


@pytest.fixture
def instrumented_client_with_prometheus(
    instrumented_client: InstrumetedCatfactClient,
    prometheus_sink: PrometheusSink,
) -> Generator[InstrumentableHttpClient, None, None]:
    with instrumented_client.instrument(prometheus_sink) as client:
        yield client
