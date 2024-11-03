from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiohttp import ClientResponse
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def parse_model(model: type[T]) -> Callable[[ClientResponse], Awaitable[T]]:
    async def _parse(response: ClientResponse) -> T:
        return model.model_validate_json(await response.read())

    return _parse
