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
    async def _parse(response: ClientResponse) -> Any:
        response_data = await response.json(loads=loads)
        if iscoroutinefunction(parser):
            return await parser(response_data)
        else:
            return parser(response_data)

    return _parse
