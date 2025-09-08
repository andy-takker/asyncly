import json
from typing import Final

from asyncly.srvmocker.serialization.base import Serializer

JsonSerializer: Final = Serializer(
    dumps=json.dumps,
    content_type="application/json",
)
