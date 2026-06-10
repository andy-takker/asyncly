from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiohttp import ClientResponse
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def parse_model(model: type[T]) -> Callable[[ClientResponse], Awaitable[T]]:
    """Build a response handler that validates the body into a Pydantic model.

    Requires the ``pydantic`` extra.

    Args:
        model: The `pydantic.BaseModel` subclass to validate the JSON body into.

    Returns:
        An async handler usable as a value in a response-handlers mapping.

    Raises:
        pydantic.ValidationError: If the body does not match the model.
    """

    async def _parse(response: ClientResponse) -> T:
        return model.model_validate_json(await response.read())

    return _parse
