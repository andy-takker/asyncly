# Instrumentation & metrics

[`InstrumentableHttpClient`][asyncly.client.metrics.instrumentable_client.InstrumentableHttpClient]
extends [`BaseHttpClient`](http-client.md) with request metrics — latency,
status, and error counts — emitted through a pluggable **sink**. When no sink is
enabled it behaves exactly like `BaseHttpClient` with negligible overhead.

Subclass it the same way you would `BaseHttpClient`:

```python
from asyncly.client.metrics.instrumentable_client import InstrumentableHttpClient


class CatfactClient(InstrumentableHttpClient):
    ...
```

## Enabling a sink

```python
client.enable_metrics(sink)
client.disable_metrics()
```

Or scope metrics to a block with the context manager:

```python
with client.instrument(sink):
    await client.fetch_fact()
```

Each completed request calls `sink.observe_request(...)` with the client name,
method, resolved route, status, duration, and error type.

## Sinks

### Prometheus

Requires the `prometheus` extra.
[`PrometheusSink`][asyncly.client.metrics.sinks.prometheus.PrometheusSink]
records a histogram of request durations labeled by client, method, route, and
status:

```python
from asyncly.client.metrics.sinks.prometheus import PrometheusSink

sink = PrometheusSink(namespace="asyncly", subsystem="client")
client.enable_metrics(sink)
```

### OpenTelemetry

Requires the `opentelemetry` extra.
[`OpenTelemetrySink`][asyncly.client.metrics.sinks.opentelemetry.OpenTelemetrySink]
records through an OpenTelemetry `Meter`:

```python
from opentelemetry import metrics
from asyncly.client.metrics.sinks.opentelemetry import OpenTelemetrySink

sink = OpenTelemetrySink(meter=metrics.get_meter("asyncly"))
client.enable_metrics(sink)
```

### Noop

[`NoopSink`][asyncly.client.metrics.sinks.noop.NoopSink] is the default — it does
nothing and adds no overhead.

## Route labels

To avoid high-cardinality metrics, request paths are normalized into a route
label by [`default_route_resolver`][asyncly.client.metrics.route_resolver.default_route_resolver],
which replaces numeric and UUID path segments with `:id` (so `/cats/42` becomes
`/cats/:id`). Pass your own `route_resolver` to `enable_metrics` /
`instrument` to customize this.

## Custom sinks

Any object implementing the
[`MetricsSink`][asyncly.client.metrics.sinks.base.MetricsSink] protocol works:

```python
class LoggingSink:
    def observe_request(
        self, *, client, method, route, status, duration_seconds, error_type=None
    ) -> None:
        print(f"{client} {method} {route} -> {status} in {duration_seconds:.3f}s")
```
