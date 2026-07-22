# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2026-07-22

### Added
- **Policy-driven retries** for `BaseHttpClient`: pass an immutable
  `RetryPolicy` to `_make_req(retry=...)` to configure attempt limits,
  retryable statuses/exceptions, allowed methods, backoff, and `Retry-After`.
  Safe defaults cover idempotent methods only. Streaming and other
  non-replayable bodies are never sent twice.
- Immutable `RetryContext` / `RetryEvent` values and an optional
  `retry_observer=` callback reporting `scheduled`, `suppressed`, and
  `exhausted` decisions.
- `DisconnectResponse` and `TruncatedResponse` socket-level fault primitives;
  `LatencyResponse` is now exported directly from `asyncly.srvmocker` too.
- Immutable `RecordedRequest` snapshots in mock-service and proxy history,
  including method, URL/path, headers, query/path parameters, body, and selected
  handler. `RequestHistory` remains as a deprecated compatibility alias.
- `MissingResponseError` replaces the opaque `KeyError` produced when a route
  is selected without a registered response.

### Changed (breaking)
- `MockService.register()` now raises `UnknownHandlerError` immediately for a
  name not declared by any `MockRoute`.
- Request history no longer retains a live `aiohttp.BaseRequest`; use the
  immutable fields on `RecordedRequest` (`call.method`, `call.headers`, etc.).
- Instrumented retrying clients record every physical attempt independently.
  A logical `503 -> 200` request therefore produces two request observations.

## [0.8.0] - 2026-07-14

### Added
- **In-flight requests metric**: `http_client_in_flight` gauge (Prometheus, with
  `multiprocess_mode="livesum"`) / up-down counter (OpenTelemetry), driven by new
  optional `on_request_start` / `on_request_end` hooks on `MetricsSink`. Existing
  sinks that don't implement these hooks are unaffected — the client
  feature-detects them once, when the sink is enabled.
- **`operation` label**: `_make_req` accepts an optional keyword-only
  `operation=` so endpoint methods can emit a stable logical-operation label
  (e.g. `operation="get_wallet_balance"`). Falls back to the resolved route.
- **Normalized `outcome` / `error_type`** via `asyncly.client.metrics.taxonomy`:
  transport failures map to a fixed vocabulary (`timeout`, `network_error`,
  `cancelled`, …) instead of raw exception class names. A failure *after* a
  response arrived (deserialization/validation) is reported as
  `outcome="response"`, `error_type="invalid_response"` with the real status.
- `BaseMetricsSink` convenience base providing no-op lifecycle hooks.
- **Network-phase metrics** via `build_trace_config(sink)`: an aiohttp
  `TraceConfig` the caller attaches to their `ClientSession`, emitting
  `http_client_phase_duration_seconds{operation, phase}` for `dns`, `pool_wait`,
  `connect`, `ttfb`, and `body_read`. Reused connections skip dns/connect (no
  zero samples). Driven by a new optional `observe_phase` sink hook; the client
  wires per-request labels through aiohttp's `trace_request_ctx` automatically.
- **Connection-pool metrics**: `PrometheusPoolCollector(upstream=...)` exposes
  `http_client_pool_connections{upstream, state}` (`active`/`idle`) from a bound
  `TCPConnector`. Reads private aiohttp internals defensively (degrades to no
  output if they change).
- **Lazy metrics exports** from `asyncly.client.metrics`
  (`InstrumentableHttpClient`, `MetricsSink`, `NoopSink`, `build_trace_config`,
  and — lazily, behind extras — `PrometheusSink`, `PrometheusPoolCollector`,
  `OpenTelemetrySink`).

### Changed (breaking)
- **Default Prometheus metric names renamed** `asyncly_client_*` →
  `http_client_*` (now consistent with the OpenTelemetry sink and the
  `http_client_*` convention). Dashboards/alerts referencing the old names must
  update. To keep the old names, construct `PrometheusSink(namespace="asyncly")`.
- **`status` label removed from the duration histogram** (it multiplied the
  time-series count by the bucket count). The histogram now carries a compact
  `outcome="response|error"`; the full `status` and 4-way `outcome` remain on the
  `*_requests_total` counter.
- **`MetricsSink.observe_request` signature** gained keyword-only `operation` and
  `outcome`. Sinks pinned to the old signature must add these parameters.
- Cancelled requests are now correctly classified (`outcome="cancelled"`); the
  previous `except Exception` never caught `asyncio.CancelledError`.

## [0.7.1] - 2026-06-10

No functional changes to the library — documentation and packaging only.

### Added
- **Documentation site** built with MkDocs Material and published to GitHub
  Pages at <https://andy-takker.github.io/asyncly/> (versioned via `mike`):
  Overview, Installation, Quickstart, a testing-strategies page, usage guides
  for every subsystem, and an autogenerated API reference (mkdocstrings).
- Google-style docstrings across the public API.
- `Documentation` URL in the project metadata (shown on PyPI).

### Changed
- Rewrote `README.rst` as a slim, friendly `README.md` landing that links to
  the full documentation.

## [0.7.0] - 2026-06-10

### Added
- **Proxy support in `BaseHttpClient`**: new keyword-only `proxy` and
  `proxy_auth` arguments (also on `InstrumentableHttpClient`). Set them once on
  the client or override per request; both are forwarded to aiohttp.
- **Forwarding mock proxy** `start_proxy(*, auth=...)` and `MockProxyService` in
  `asyncly.srvmocker`. Spins up an in-process HTTP proxy that records every
  request passing through it and forwards it to the real target, so tests can
  assert a client genuinely routes through a proxy. Supports `Proxy-Authorization`
  validation (returns `407` and does not forward on mismatch). Mirrors
  `MockService`'s assertion helpers (`assert_called`, `assert_not_called`,
  `get_calls`, `last_call`). HTTP targets only (no `CONNECT`/HTTPS tunnelling).
- **`mock_proxy` pytest fixture** exposing a ready-to-use forwarding proxy.

## [0.6.2] - 2026-05-11

### Security
- Re-release of 0.6.1 with the `aiohttp>=3.13.3` constraint actually
  included in the published wheel. Version 0.6.1 was tagged before the
  dependency bump from
  [#29](https://github.com/andy-takker/asyncly/pull/29) merged, so the
  uploaded artifact still allowed vulnerable `aiohttp<3.13.3`. Both
  0.6.0 and 0.6.1 are yanked from PyPI. Install `asyncly>=0.6.2` to
  receive the [CVE-2025-69223](https://nvd.nist.gov/vuln/detail/CVE-2025-69223)
  mitigation.

## [0.6.1] - 2026-05-11

### Security
- Bump minimum `aiohttp` to `>=3.13.3` to address
  [CVE-2025-69223](https://nvd.nist.gov/vuln/detail/CVE-2025-69223): a
  zip-bomb DoS in `aiohttp`'s handling of compressed request/response
  bodies (affects aiohttp `<= 3.13.2`). Thanks to
  [@loganaden](https://github.com/loganaden) for the report and fix
  ([#29](https://github.com/andy-takker/asyncly/pull/29)).

## [0.6.0] - 2026-05-11

### Added
- **Pytest plugin** (`asyncly.pytest_plugin`) auto-registered via `pytest11` entry-point. Provides `mock_routes` and `mock_service` fixtures so tests no longer need to wire their own `start_service` context manager.
- **Request matching** via the new `Match` builder on `MockRoute`. Multiple routes can share `(method, path)` and be dispatched by JSON body, headers (subset), query (subset), or raw body. Routes without `match=` act as fallbacks within their group.
- **Assertion helpers on `MockService`**: `get_calls(name)`, `last_call(name)`, `assert_called(name, *, times=, json=, body=, headers=, query=)`, `assert_not_called(name)`.
- **`RawResponse`** for returning arbitrary bytes with arbitrary headers — useful for testing client behavior on malformed JSON or unexpected content types.
- **TLS support** in `start_service(routes, *, ssl_context=...)` — pass an `ssl.SSLContext` to serve over HTTPS (`MockService.url.scheme == "https"`).
- `SequenceResponse(on_exhausted=...)` with three modes: `"raise"` (default, new behavior raises `SequenceExhausted` with a clear message), `"cycle"`, `"last"`. Now exported directly from `asyncly.srvmocker`.
- New exceptions: `SrvMockerError`, `SequenceExhausted`, `UnknownHandlerError`.

### Changed
- `MockService.register()` now emits `DeprecationWarning` when called with a `handler_name` not declared in any `MockRoute`. Will become `UnknownHandlerError` in 0.7.
- `SequenceResponse` on exhaustion now raises a typed `SequenceExhausted` instead of bubbling `RuntimeError` from PEP 479. Default behavior otherwise unchanged.
- `Match` defensively copies `headers` and `query` dict arguments at construction time — caller-side mutation of the original dict no longer affects matcher behavior.

### Fixed
- `SequenceResponse([])` now raises `ValueError` eagerly instead of failing on first use.

[Unreleased]: https://github.com/andy-takker/asyncly/compare/0.9.0...HEAD
[0.9.0]: https://github.com/andy-takker/asyncly/compare/0.8.0...0.9.0
[0.8.0]: https://github.com/andy-takker/asyncly/compare/0.7.1...0.8.0
[0.7.1]: https://github.com/andy-takker/asyncly/compare/0.7.0...0.7.1
[0.7.0]: https://github.com/andy-takker/asyncly/compare/0.6.2...0.7.0
[0.6.2]: https://github.com/andy-takker/asyncly/compare/0.6.1...0.6.2
[0.6.1]: https://github.com/andy-takker/asyncly/compare/0.6.0...0.6.1
[0.6.0]: https://github.com/andy-takker/asyncly/compare/0.5.1...0.6.0
