from typing import Final

try:
    import toml
except ImportError:
    raise ImportError("toml is not installed")

from asyncly.srvmocker.serialization.base import Serializer

TomlSerializer: Final = Serializer(
    dumps=toml.dumps,
    content_type="application/toml",
)
