# Responses & serializers

A **response** is what the [mock server](mock-server.md) returns for a handler.
You register one with `service.register(name, response)`. All responses derive
from [`BaseMockResponse`][asyncly.srvmocker.BaseMockResponse], so you can write
your own too.

## JsonResponse

[`JsonResponse`][asyncly.srvmocker.JsonResponse] serializes any object to a JSON
body:

```python
from asyncly.srvmocker import JsonResponse

service.register("fact", JsonResponse({"fact": "Meow.", "length": 5}))
service.register("missing", JsonResponse({"error": "not found"}, status=404))
```

## RawResponse

[`RawResponse`][asyncly.srvmocker.RawResponse] returns arbitrary bytes with
arbitrary headers — ideal for testing client behavior on malformed payloads,
unexpected content types, or empty bodies:

```python
from asyncly.srvmocker import RawResponse

service.register(
    "broken_json",
    RawResponse(
        body=b'{"truncated":',
        status=200,
        headers={"Content-Type": "application/json"},
    ),
)
```

## SequenceResponse

[`SequenceResponse`][asyncly.srvmocker.SequenceResponse] returns a different
response on each call, in order — useful for testing retries and pagination. The
`on_exhausted` argument controls what happens after the last response:

```python
from asyncly.srvmocker import JsonResponse, SequenceResponse

service.register(
    "flaky",
    SequenceResponse(
        [
            RawResponse(status=503),
            RawResponse(status=503),
            JsonResponse({"ok": True}),
        ],
        on_exhausted="last",  # "raise" (default), "cycle", or "last"
    ),
)
```

- `"raise"` (default) — raise [`SequenceExhausted`][asyncly.srvmocker.SequenceExhausted]
  on the next call (surfaces to the client as a `500`).
- `"cycle"` — loop back to the first response.
- `"last"` — keep returning the last response forever.

Constructing with an empty list raises `ValueError` eagerly.

## LatencyResponse

[`LatencyResponse`][asyncly.srvmocker.responses.timeout.LatencyResponse] wraps
another response and delays it — the tool for testing timeouts:

```python
from asyncly.srvmocker import JsonResponse
from asyncly.srvmocker.responses.timeout import LatencyResponse

service.register(
    "slow",
    LatencyResponse(wrapped=JsonResponse({"ok": True}), latency=1.5),
)
```

```python
import asyncio
import pytest

with pytest.raises(asyncio.TimeoutError):
    await client.fetch_fact(timeout=0.1)
```

## Other formats

For non-JSON wire formats, register the matching response (each takes the same
`body`, `status`, `headers` arguments as `JsonResponse`):

| Response | Format | Extra / dependency |
| --- | --- | --- |
| [`MsgpackResponse`][asyncly.srvmocker.responses.msgpack.MsgpackResponse] | msgpack | `msgspec` |
| [`TomlResponse`][asyncly.srvmocker.responses.toml.TomlResponse] | TOML | `toml` |
| [`YamlResponse`][asyncly.srvmocker.responses.yaml.YamlResponse] | YAML | `pyyaml` |

## ContentResponse and serializers

[`ContentResponse`][asyncly.srvmocker.ContentResponse] is the general form: a body
plus an explicit [`Serializer`][asyncly.srvmocker.serialization.base.Serializer]
that pairs a `dumps` callable with a content type. The format-specific responses
above are thin wrappers over it. Use it to plug in a custom serializer:

```python
from asyncly.srvmocker import ContentResponse
from asyncly.srvmocker.serialization.json import JsonSerializer

service.register(
    "custom",
    ContentResponse(body={"ok": True}, serializer=JsonSerializer),
)
```

Built-in serializers: `JsonSerializer`, `MsgpackSerializer`, `TomlSerializer`,
`YamlSerializer`. See the [serializers reference](../reference/serializers.md).
