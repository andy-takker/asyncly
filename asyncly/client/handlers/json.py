from asyncio import iscoroutinefunction
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientResponse

try:
    import orjson as json
except ImportError:
    import json  # type: ignore


def parse_json(
    parser: Callable,
    loads: Callable = json.loads,
) -> Callable[[ClientResponse], Awaitable[Any]]:
    """Build a response handler that decodes JSON and passes it to ``parser``.

    Args:
        parser: Callable applied to the decoded JSON. May be sync or async.
            Use ``lambda data: data`` to return the parsed value unchanged.
        loads: JSON loader. Defaults to `orjson.loads` when the ``orjson``
            extra is installed, otherwise the stdlib `json.loads`.

    Returns:
        An async handler usable as a value in a response-handlers mapping.
    """

    async def _parse(response: ClientResponse) -> Any:
        response_data = await response.json(loads=loads)
        if iscoroutinefunction(parser):
            return await parser(response_data)
        else:
            return parser(response_data)

    return _parse
