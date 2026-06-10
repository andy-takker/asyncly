# Testing strategies

When your service talks to an upstream API, you need to test that integration
without depending on the real upstream. There are several ways to do it, trading
**realism** against **setup cost**. asyncly sits at the realistic end of that
spectrum — and this page explains when that's worth it.

## The ladder of realism

Think of mocking strategies as rungs on a ladder. Each rung exercises more of the
real network stack than the one below it.

1. **Dependency-injection override.** Replace the client object with a fake in
   your DI container. Zero network, fastest, but you test your fake — not your
   real client, its serialization, or its error handling.
2. **Transport patching** (`aioresponses`, `respx`). Monkeypatch the HTTP
   library's transport so requests resolve to canned responses. Fast and
   convenient, but no socket is opened: real timeouts, connection limits, header
   auto-injection, and streaming behavior are bypassed.
3. **Record / replay** (`vcrpy`). Record real HTTP interactions once into
   "cassettes" and replay them. Realistic payloads, but requires access to the
   real upstream to record, and cassettes drift out of date.
4. **Real WSGI server** (`pytest-httpserver`). Spin up an actual werkzeug server
   in a thread with a rich expectations API. Real sockets, but a synchronous
   server living outside your asyncio loop.
5. **Real ASGI/aiohttp server in the same loop** (`asyncly.srvmocker`). Run a
   genuine `aiohttp.TestServer` inside your test's event loop. Real sockets, real
   timeouts, real aiohttp behavior — with responses you control per test.

## Comparison

| Tool | Mechanism | Real HTTP | Coupled to | Best for |
| --- | --- | --- | --- | --- |
| `aioresponses` | Patches aiohttp transport | No | aiohttp | Fast unit tests without timeouts / streaming |
| `respx` | Patches httpx transport | No | httpx | Same, for httpx |
| `vcrpy` | Record / replay cassettes | Yes (on first record) | aiohttp, httpx, requests | When the real API is available |
| `pytest-httpserver` | Real WSGI server (werkzeug, thread) | Yes | Any | Sync / mixed stacks with rich expectations |
| `asyncly.srvmocker` | Real aiohttp test server, same loop | Yes | Any (best with aiohttp) | Async aiohttp apps needing realistic latencies / WS / SSE |

## When to reach for asyncly

`srvmocker` runs a real `aiohttp.TestServer` in your test loop, so it catches
classes of bugs the patching libraries miss — real sockets, real timeouts,
header auto-injection, and serialization quirks — and it pairs naturally with the
bundled [`BaseHttpClient`](../guide/http-client.md).

It shines when you want to test:

- **Timeouts and latency** — use [`LatencyResponse`](../guide/responses.md#latencyresponse)
  to make the server slow and assert your client gives up.
- **Realistic error handling** — return real status codes and malformed bodies
  with [`RawResponse`](../guide/responses.md#rawresponse).
- **What your client actually sent** — assert on the recorded
  [request history](../guide/mock-server.md#asserting-what-your-client-sent).
- **Proxies and TLS** — route through a [mock proxy](../guide/proxy-testing.md)
  or serve [over HTTPS](../guide/mock-server.md#https-tls).

## When to pick something else

- **Dozens of pure unit tests of retry logic** — `aioresponses` or `respx` are
  cheaper to set up.
- **A synchronous codebase**, or you need WireMock-style expectations across
  multiple HTTP clients — `pytest-httpserver`.
- **You have the real upstream** and want golden recordings — `vcrpy`.

The trade-off is always realism vs. setup cost. asyncly chooses realism while
keeping setup small — a context manager and a few route declarations.
