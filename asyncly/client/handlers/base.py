from collections.abc import Callable, Mapping
from http import HTTPStatus
from typing import Any

from aiohttp import ClientResponse

from asyncly.client.handlers.exceptions import UnhandledStatusException

ResponseHandlersType = Mapping[HTTPStatus | int | str, Callable]


async def apply_handler(
    handlers: ResponseHandlersType,
    response: ClientResponse,
    client_name: str,
) -> Any:
    handler = _find_handler(handlers=handlers, status=response.status)
    if not handler:
        raise UnhandledStatusException(
            f"Unexpected resposne {response.status} from {response.url}",
            status=response.status,
            url=response.url,
            client_name=client_name,
        )
    return await handler(response=response)


def _find_handler(handlers: ResponseHandlersType, status: int) -> Callable | None:
    if status in handlers:
        return handlers[status]

    status_group = f"{status // 100}xx"
    if status_group in handlers:
        return handlers[status_group]

    if "*" in handlers:
        return handlers["*"]

    return None
