import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final


@dataclass(frozen=True)
class Serializer:
    dumps: Callable[[Any], str]
    content_type: str


JsonSerializer: Final = Serializer(
    dumps=json.dumps,
    content_type="application/json",
)
