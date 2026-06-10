from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol, TypeVar

from aiohttp import ClientResponse
from msgspec import Struct
from msgspec.json import decode as decode_json
from msgspec.msgpack import decode as decode_msgpack
from msgspec.toml import decode as decode_toml
from msgspec.yaml import decode as decode_yaml

T = TypeVar("T", bound=Struct)

DataFormat = Literal["json", "msgpack", "toml", "yaml"]


class DataFormatDecode(Protocol):
    def __call__(
        self,
        buf: bytes | str,
        *,
        type: type[T] = ...,
        strict: bool = True,
        dec_hook: Callable[[type, Any], Any] | None = None,
    ) -> Any: ...


def parse_struct(
    struct: type[T],
    data_format: DataFormat = "json",
    strict: bool = True,
) -> Callable[[ClientResponse], Awaitable[T]]:
    """Build a response handler that decodes the body into a msgspec struct.

    Requires the ``msgspec`` extra.

    Args:
        struct: The `msgspec.Struct` subclass to decode into.
        data_format: Wire format of the body: ``"json"``, ``"msgpack"``,
            ``"toml"``, or ``"yaml"``.
        strict: Pass-through to msgspec strict decoding (no implicit coercion).

    Returns:
        An async handler usable as a value in a response-handlers mapping.

    Raises:
        msgspec.ValidationError: If the payload does not match ``struct``.
    """
    decode = _choose_decoder(data_format)

    async def _parse(response: ClientResponse) -> T:
        return decode(await response.read(), type=struct, strict=strict)

    return _parse


def _choose_decoder(data_format: DataFormat) -> DataFormatDecode:
    if data_format == "json":
        return decode_json  # type: ignore[return-value]
    elif data_format == "msgpack":
        return decode_msgpack  # type: ignore[return-value]
    elif data_format == "toml":
        return decode_toml
    elif data_format == "yaml":
        return decode_yaml
    return decode_json
