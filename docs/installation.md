# Installation

asyncly requires **Python 3.10+** and depends only on
[aiohttp](https://docs.aiohttp.org/).

## From PyPI

```bash
pip install asyncly
```

## From GitHub

```bash
pip install git+https://github.com/andy-takker/asyncly
```

## Extras

Install optional features by naming them in brackets. For example, to parse
responses into Pydantic models:

```bash
pip install "asyncly[pydantic]"
```

| Extra | Install | Enables |
| --- | --- | --- |
| `msgspec` | `pip install "asyncly[msgspec]"` | Parse responses into [msgspec](https://github.com/jcrist/msgspec) structs |
| `pydantic` | `pip install "asyncly[pydantic]"` | Parse responses into [Pydantic](https://github.com/pydantic/pydantic) models |
| `orjson` | `pip install "asyncly[orjson]"` | Fast JSON parsing via [orjson](https://github.com/ijl/orjson) |
| `prometheus` | `pip install "asyncly[prometheus]"` | [Prometheus](https://prometheus.io) client metrics |
| `opentelemetry` | `pip install "asyncly[opentelemetry]"` | [OpenTelemetry](https://opentelemetry.io) metrics |

You can combine extras:

```bash
pip install "asyncly[pydantic,prometheus]"
```

## Next steps

- [Quickstart](quickstart.md) — build and test a client in a few minutes.
- [Usage guide](guide/http-client.md) — dive into each subsystem.
