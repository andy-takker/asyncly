from typing import Final

import msgspec

from asyncly.srvmocker.serialization.base import Serializer

MsgpackSerializer: Final = Serializer(
    dumps=msgspec.msgpack.encode,
    content_type="application/msgpack",
)
