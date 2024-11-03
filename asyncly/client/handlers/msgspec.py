from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiohttp import ClientResponse
from msgspec import Struct
from msgspec.json import decode

T = TypeVar("T", bound=Struct)


def parse_struct(struct: type[T]) -> Callable[[ClientResponse], Awaitable[T]]:
    async def _parse(response: ClientResponse) -> T:
        return decode(await response.read(), type=struct)

    return _parse
