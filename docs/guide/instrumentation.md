# Instrumentation & metrics

[`InstrumentableHttpClient`][asyncly.client.metrics.instrumentable_client.InstrumentableHttpClient]
extends [`BaseHttpClient`](http-client.md) with request metrics emitted through a
pluggable **sink**. When no sink is enabled it behaves exactly like
`BaseHttpClient` with negligible overhead.

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

## Metrics emitted

| Metric | Type | Labels |
| --- | --- | --- |
| `http_client_requests_total` | counter | `client, method, route, operation, status, outcome` |
| `http_client_request_seconds` | histogram | `client, method, route, operation, outcome` |
| `http_client_errors_total` | counter | `client, method, route, operation, error_type` |
| `http_client_in_flight` | gauge | `client, method, route, operation` |
| `http_client_phase_duration_seconds` | histogram | `client, operation, phase` |
| `http_client_pool_connections` | gauge | `upstream, state` |

`status` is intentionally kept **off** the duration histogram — each extra label
multiplies the series count by the number of buckets. The histogram carries a
compact `outcome` of `response` or `error` instead; the full status and 4-way
`outcome` (`response`, `timeout`, `network_error`, `cancelled`) live on the
counter.

A failure that happens *after* a response arrived (deserialization/validation,
or an unhandled status) is reported as `outcome="response"` with the real status
and `error_type="invalid_response"` — so 5xx and latency math on the physical
request stay correct.

## `operation` label

`operation` is a stable, low-cardinality logical name. Pass it per endpoint:

```python
async def get_wallet_balance(self):
    return await self._make_req(
        method=hdrs.METH_GET,
        url=self._url / "v5/account/wallet-balance",
        handlers=self.BALANCE_HANDLERS,
        operation="get_wallet_balance",
    )
```

It defaults to the resolved route when omitted.

## Sinks

### Prometheus

Requires the `prometheus` extra. The default metric prefix is `http_client_*`.

```python
from asyncly.client.metrics.sinks.prometheus import PrometheusSink

sink = PrometheusSink()  # -> http_client_*
client.enable_metrics(sink)
```

!!! warning "Breaking change"
    The default metric names changed from `asyncly_client_*` to `http_client_*`.
    To keep the old names on upgrade, construct
    `PrometheusSink(namespace="asyncly", subsystem="client")`.

Under Gunicorn/multiprocess, the in-flight gauge uses
`multiprocess_mode="livesum"`; configure `PROMETHEUS_MULTIPROC_DIR` and a
`MultiProcessCollector` as usual.

### OpenTelemetry

Requires the `opentelemetry` extra. Metric names match the Prometheus defaults.

```python
from opentelemetry import metrics
from asyncly.client.metrics.sinks.opentelemetry import OpenTelemetrySink

sink = OpenTelemetrySink(meter=metrics.get_meter("asyncly"))
client.enable_metrics(sink)
```

### Noop

[`NoopSink`][asyncly.client.metrics.sinks.noop.NoopSink] is the default — it does
nothing and adds no overhead.

## Network phases & connection pool (semi-automatic)

Phase timings (`dns`, `pool_wait`, `connect`, `ttfb`, `body_read`) and pool
stats come from aiohttp's `TraceConfig` and connector. Because the session is
injected, the library supplies the `TraceConfig`; you wire it in when
constructing the session:

```python
from aiohttp import ClientSession, TCPConnector
from asyncly.client.metrics.sinks.prometheus import (
    PrometheusSink,
    PrometheusPoolCollector,
)
from asyncly.client.metrics.trace_config import build_trace_config

sink = PrometheusSink()
connector = TCPConnector(limit=100)
session = ClientSession(
    connector=connector,
    trace_configs=[build_trace_config(sink)],
)

pool = PrometheusPoolCollector(upstream="bybit")
pool.bind(connector)  # registers with the default registry lazily via collect()

client = CatfactClient(url, session, "bybit")
client.enable_metrics(sink)
```

Per-request labels (`client`, `operation`) flow through aiohttp's
`trace_request_ctx`, which the client sets automatically when the sink implements
`observe_phase`. Reused connections skip `dns`/`connect` (no zero samples). Pool
stats are **connector-scoped** — a connector shared by several clients cannot
attribute connections to one of them.

## Route labels

Request paths are normalized into a route label by
[`default_route_resolver`][asyncly.client.metrics.route_resolver.default_route_resolver],
which replaces numeric and UUID path segments with `:id` (so `/cats/42` becomes
`/cats/:id`). Pass your own `route_resolver` to `enable_metrics` / `instrument`
to customize this.

## Custom sinks

Any object implementing the
[`MetricsSink`][asyncly.client.metrics.sinks.base.MetricsSink] protocol works.
Only `observe_request` is required; `on_request_start` / `on_request_end`
(in-flight) and `observe_phase` (phases) are optional and feature-detected when
the sink is enabled.

```python
class LoggingSink:
    def observe_request(
        self, *, client, method, route, operation,
        status, outcome, duration_seconds, error_type=None,
    ) -> None:
        print(f"{client} {operation} -> {status} ({outcome}) in {duration_seconds:.3f}s")
```

!!! note
    The `observe_request` signature gained keyword-only `operation` and
    `outcome`. Sinks written against the older signature must add them.
