from collections.abc import Generator

import pytest
from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricReader
from opentelemetry.sdk.resources import Resource

from asyncly.client.metrics.instrumentable_client import InstrumentableHttpClient
from asyncly.client.metrics.sinks.opentelemetry import OpenTelemetrySink
from tests.plugins.instrumented_client import InstrumetedCatfactClient


@pytest.fixture
def otel_reader() -> MetricReader:
    return InMemoryMetricReader()


@pytest.fixture
def otel_provider(otel_reader: MetricReader) -> MeterProvider:
    return MeterProvider(
        resource=Resource.create({"service.name": "tests.instrumentable-client"}),
        metric_readers=[otel_reader],
    )


@pytest.fixture
def otel_meter(otel_provider: MeterProvider) -> Meter:
    return otel_provider.get_meter("tests.meter")


@pytest.fixture
def otel_sink(otel_meter: Meter) -> OpenTelemetrySink:
    return OpenTelemetrySink(meter=otel_meter)


@pytest.fixture
def instrumented_client_with_opentelemetry(
    instrumented_client: InstrumetedCatfactClient,
    otel_sink: OpenTelemetrySink,
) -> Generator[InstrumentableHttpClient, None, None]:
    with instrumented_client.instrument(otel_sink) as client:
        yield client


def collect_points(reader: InMemoryMetricReader):
    data = reader.get_metrics_data()
    out = {}
    for res_scope in data.resource_metrics:
        for scope in res_scope.scope_metrics:
            for metric in scope.metrics:
                name = metric.name
                points = []
                if metric.data.data_points:
                    for p in metric.data.data_points:
                        attrs = (
                            dict(p.attributes) if getattr(p, "attributes", None) else {}
                        )
                        if (
                            metric.data.__class__.__name__.lower().find("histogram")
                            >= 0
                        ):
                            points.append(
                                (
                                    attrs,
                                    {
                                        "sum": getattr(p, "sum", None),
                                        "count": getattr(p, "count", None),
                                        "bounds": getattr(p, "bucket_counts", None),
                                    },
                                )
                            )
                        else:
                            val = getattr(p, "value", None)
                            points.append((attrs, val))
                out[name] = points
    return out
