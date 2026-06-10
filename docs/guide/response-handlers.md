# Response handlers

A **response handler** turns an `aiohttp.ClientResponse` into a Python value.
You map status codes to handlers, and `_make_req` picks the one matching the
response status.

```python
ResponseHandlersType = Mapping[HTTPStatus | int | str, ResponseHandler]
```

A handler mapping is usually a `MappingProxyType` (an immutable dict) declared
as a class attribute:

```python
from http import HTTPStatus
from types import MappingProxyType

from asyncly import ResponseHandlersType
from asyncly.client.handlers.pydantic import parse_model

FACT_HANDLERS: ResponseHandlersType = MappingProxyType(
    {HTTPStatus.OK: parse_model(CatFact)}
)
```

## Status matching

Keys are matched in order of specificity:

- **Exact** — `HTTPStatus.OK` or `200`.
- **Range** — the string `"2xx"`, `"4xx"`, `"5xx"` matches any status in that
  hundred.
- **Wildcard** — the string `"*"` matches any status not matched above.

```python
HANDLERS = MappingProxyType(
    {
        HTTPStatus.OK: parse_model(CatFact),
        "4xx": raise_client_error,
        "*": raise_unexpected,
    }
)
```

## Built-in handler factories

Each factory returns a handler — call it with the type you want to decode into.

### JSON

[`parse_json`][asyncly.client.handlers.json.parse_json] decodes the body as JSON
and passes it to a `parser` callable:

```python
from asyncly.client.handlers.json import parse_json

# identity: return the parsed dict/list as-is
HANDLERS = {HTTPStatus.OK: parse_json(lambda data: data)}

# or transform it
HANDLERS = {HTTPStatus.OK: parse_json(lambda data: data["facts"])}
```

If the [`orjson`](https://github.com/ijl/orjson) extra is installed, it is used
automatically for faster parsing.

### Pydantic

[`parse_model`][asyncly.client.handlers.pydantic.parse_model] validates the JSON
body into a Pydantic model (requires the `pydantic` extra):

```python
from pydantic import BaseModel
from asyncly.client.handlers.pydantic import parse_model


class CatFact(BaseModel):
    fact: str
    length: int


HANDLERS = {HTTPStatus.OK: parse_model(CatFact)}
```

### msgspec

[`parse_struct`][asyncly.client.handlers.msgspec.parse_struct] decodes into a
msgspec struct (requires the `msgspec` extra) and supports multiple wire
formats:

```python
from msgspec import Struct
from asyncly.client.handlers.msgspec import parse_struct


class CatFact(Struct):
    fact: str
    length: int


# JSON body
HANDLERS = {HTTPStatus.OK: parse_struct(CatFact)}

# msgpack body
HANDLERS = {HTTPStatus.OK: parse_struct(CatFact, data_format="msgpack")}
```

## Custom handlers

A handler is just an async callable taking the response. Write your own for raw
bytes, headers, or side effects:

```python
from aiohttp import ClientResponse


async def read_etag(response: ClientResponse) -> str:
    return response.headers["ETag"]


HANDLERS = {HTTPStatus.OK: read_etag}
```

## Handling errors

Map error statuses to handlers that raise domain exceptions:

```python
from aiohttp import ClientResponse


async def raise_not_found(response: ClientResponse) -> None:
    raise CatNotFound(await response.text())


HANDLERS = MappingProxyType(
    {
        HTTPStatus.OK: parse_model(CatFact),
        HTTPStatus.NOT_FOUND: raise_not_found,
    }
)
```

If a status has **no** matching handler,
[`UnhandledStatusException`][asyncly.client.handlers.exceptions.UnhandledStatusException]
is raised with the `status`, `url`, and `client_name`.
