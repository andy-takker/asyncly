# asyncly

**A tiny async HTTP client and a *real* aiohttp mock server for testing your
integrations — built on [aiohttp](https://docs.aiohttp.org/).**

asyncly is two small, composable pieces:

<div class="grid cards" markdown>

-   :material-cloud-upload: **HTTP client**

    ---

    `BaseHttpClient` — a thin, typed base class for writing API clients. Map
    status codes to response handlers, parse into Pydantic / msgspec / JSON,
    set flexible timeouts, and route through a proxy.

    [:octicons-arrow-right-24: HTTP client guide](guide/http-client.md)

-   :material-server-network: **Mock server**

    ---

    `srvmocker` runs a **real** `aiohttp.TestServer` inside your test loop —
    not a transport patch. Simulate upstreams, swap responses per test, and
    assert exactly what your client sent.

    [:octicons-arrow-right-24: Mock server guide](guide/mock-server.md)

</div>

## Why a real server instead of patching?

Transport-patching mocks (`aioresponses`, `respx`) are fast but never touch a
socket — they miss real timeouts, header auto-injection, connection handling,
and serialization quirks. asyncly serves a genuine aiohttp server in the same
event loop, so your client exercises the real network stack.

See [Testing strategies](why/testing-strategies.md) for the full comparison.

## Features

- **Typed client base** with per-status [response handlers](guide/response-handlers.md)
  (JSON, Pydantic, msgspec).
- **Real mock server** via [`start_service`](guide/mock-server.md) with dynamic,
  per-test responses.
- **[Request matching](guide/request-matching.md)** — route by JSON body, headers,
  or query.
- **[Assertions](guide/mock-server.md#asserting-what-your-client-sent)** on recorded
  request history.
- **[Proxy testing](guide/proxy-testing.md)** — a forwarding mock proxy with
  `Proxy-Authorization` validation.
- **TLS**, **msgpack/TOML/YAML** responses, and **[metrics](guide/instrumentation.md)**
  (Prometheus, OpenTelemetry).
- A **[pytest plugin](guide/pytest-plugin.md)** with ready-made fixtures.

## Get started

```bash
pip install asyncly
```

Then jump into the [Quickstart](quickstart.md).
