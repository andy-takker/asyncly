from typing import Final

import yaml

from asyncly.srvmocker.serialization.base import Serializer

YamlSerializer: Final = Serializer(
    dumps=yaml.dump,
    content_type="application/yaml",
)
