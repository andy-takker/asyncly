from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Serializer:
    dumps: Callable[[Any], str | bytes]
    content_type: str
