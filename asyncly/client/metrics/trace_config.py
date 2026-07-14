"""Semi-automatic network-phase and connection-pool instrumentation.

`InstrumentableHttpClient` records everything it can see from inside `_make_req`:
the total request duration, status, outcome, and in-flight count. It cannot see
*where* the time went — DNS resolution, waiting for a pooled connection, the TCP
connect, time-to-first-byte, body read — because those happen inside aiohttp.

aiohttp exposes them through `TraceConfig`, but a `TraceConfig` must be attached
when the `ClientSession` is constructed, and the session is injected into the
client by the caller. So this instrumentation is **semi-automatic**: the library
supplies the `TraceConfig` (and an optional pool collector); the caller wires
them into their session:

    from aiohttp import ClientSession, TCPConnector
    from asyncly.client.metrics.trace_config import build_trace_config

    sink = PrometheusSink()
    session = ClientSession(
        trace_configs=[build_trace_config(sink)],
        connector=TCPConnector(limit=100),
    )
    client = MyClient(url, session, "svc")
    client.enable_metrics(sink)

Per-request labels (client, operation) travel via aiohttp's ``trace_request_ctx``,
which `InstrumentableHttpClient` populates automatically when the sink implements
``observe_phase``.
"""

from time import perf_counter
from typing import Any

from aiohttp import TraceConfig

from asyncly.client.metrics.sinks.base import MetricsSink

# Phase label values.
DNS = "dns"
POOL_WAIT = "pool_wait"
CONNECT = "connect"
TTFB = "ttfb"
BODY_READ = "body_read"


def _labels(trace_config_ctx: Any) -> tuple[str, str] | None:
    ctx = getattr(trace_config_ctx, "trace_request_ctx", None)
    if not isinstance(ctx, dict):
        return None
    client = ctx.get("client")
    operation = ctx.get("operation")
    if client is None or operation is None:
        return None
    return client, operation


class _PhaseTracer:
    """Turns aiohttp trace callbacks into ``observe_phase`` calls.

    Per-request timing is stashed on the aiohttp-provided ``trace_config_ctx``
    (a fresh `SimpleNamespace` per request), so concurrent requests never share
    state.
    """

    def __init__(self, observe: Any) -> None:
        self._observe = observe

    def _emit(self, ctx: Any, phase: str, started: float) -> None:
        labels = _labels(ctx)
        if labels is None:
            return
        client, operation = labels
        self._observe(
            client=client,
            operation=operation,
            phase=phase,
            seconds=perf_counter() - started,
        )

    def _emit_from(self, ctx: Any, attr: str, phase: str) -> None:
        started = getattr(ctx, attr, None)
        if started is not None:
            self._emit(ctx, phase, started)

    async def on_request_start(self, session: Any, ctx: Any, params: Any) -> None:
        ctx._asyncly_req_start = perf_counter()
        ctx._asyncly_first_chunk = None

    async def on_dns_start(self, session: Any, ctx: Any, params: Any) -> None:
        ctx._asyncly_dns_start = perf_counter()

    async def on_dns_end(self, session: Any, ctx: Any, params: Any) -> None:
        self._emit_from(ctx, "_asyncly_dns_start", DNS)

    async def on_pool_start(self, session: Any, ctx: Any, params: Any) -> None:
        ctx._asyncly_pool_start = perf_counter()

    async def on_pool_end(self, session: Any, ctx: Any, params: Any) -> None:
        self._emit_from(ctx, "_asyncly_pool_start", POOL_WAIT)

    async def on_connect_start(self, session: Any, ctx: Any, params: Any) -> None:
        ctx._asyncly_connect_start = perf_counter()

    async def on_connect_end(self, session: Any, ctx: Any, params: Any) -> None:
        self._emit_from(ctx, "_asyncly_connect_start", CONNECT)

    async def on_chunk_received(self, session: Any, ctx: Any, params: Any) -> None:
        if getattr(ctx, "_asyncly_first_chunk", None) is not None:
            return
        ctx._asyncly_first_chunk = perf_counter()
        self._emit_from(ctx, "_asyncly_req_start", TTFB)

    async def on_request_end(self, session: Any, ctx: Any, params: Any) -> None:
        self._emit_from(ctx, "_asyncly_first_chunk", BODY_READ)


def build_trace_config(sink: MetricsSink) -> TraceConfig:
    """Build an aiohttp `TraceConfig` that reports network phases to ``sink``.

    Attach the result to a `ClientSession(trace_configs=[...])`. Phases are only
    emitted for requests carrying a ``trace_request_ctx`` with ``client`` and
    ``operation`` keys — which `InstrumentableHttpClient` sets automatically.

    Reused connections skip the dns/connect phases entirely (aiohttp fires no
    callback), so no misleading zero-duration samples are recorded.
    """
    observe = getattr(sink, "observe_phase", None)
    trace_config = TraceConfig()
    if observe is None:
        # Sink can't record phases — return an inert TraceConfig so callers can
        # still wire it in unconditionally.
        return trace_config

    tracer = _PhaseTracer(observe)
    trace_config.on_request_start.append(tracer.on_request_start)
    trace_config.on_dns_resolvehost_start.append(tracer.on_dns_start)
    trace_config.on_dns_resolvehost_end.append(tracer.on_dns_end)
    trace_config.on_connection_queued_start.append(tracer.on_pool_start)
    trace_config.on_connection_queued_end.append(tracer.on_pool_end)
    trace_config.on_connection_create_start.append(tracer.on_connect_start)
    trace_config.on_connection_create_end.append(tracer.on_connect_end)
    trace_config.on_response_chunk_received.append(tracer.on_chunk_received)
    trace_config.on_request_end.append(tracer.on_request_end)
    return trace_config
