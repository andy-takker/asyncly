from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Serializer:
    """Pairs a serialization function with its HTTP content type.

    Used by [`ContentResponse`][asyncly.srvmocker.ContentResponse] to render a
    body. Provide your own to support a custom wire format.

    Attributes:
        dumps: Callable serializing a body to `str` or `bytes`.
        content_type: Value for the response ``Content-Type`` header.
    """

    dumps: Callable[[Any], str | bytes]
    content_type: str
