from collections.abc import AsyncIterator
from datetime import datetime

import pytest
from yarl import URL

from asyncly.srvmocker import JsonResponse
from asyncly.srvmocker.models import MockRoute, MockService
from asyncly.srvmocker.responses.msgpack import MsgpackResponse
from asyncly.srvmocker.responses.toml import TomlResponse
from asyncly.srvmocker.responses.yaml import YamlResponse
from asyncly.srvmocker.service import start_service


@pytest.fixture
async def catfact_service() -> AsyncIterator[MockService]:
    routes = [
        MockRoute("GET", "/fact/json", "json_catfact"),
        MockRoute("GET", "/fact/toml", "toml_catfact"),
        MockRoute("GET", "/fact/yaml", "yaml_catfact"),
        MockRoute("GET", "/fact/msgpack", "msgpack_catfact"),
    ]
    async with start_service(routes) as service:
        service.register(
            "json_catfact",
            JsonResponse(
                {
                    "fact": "test json",
                    "length": 1,
                    "created_at": "2025-01-01T12:15:00.000000",
                    "colors": ["red", "blue"],
                },
            ),
        )
        service.register(
            "toml_catfact",
            TomlResponse(
                {
                    "fact": "test toml",
                    "length": 2,
                    "created_at": datetime(2025, 1, 2, 12, 15),
                    "colors": ["orange", "blue"],
                },
            ),
        )
        service.register(
            "yaml_catfact",
            YamlResponse(
                {
                    "fact": "test yaml",
                    "length": 3,
                    "created_at": datetime(2025, 1, 3, 12, 15),
                    "colors": ["red", "black"],
                },
            ),
        )
        service.register(
            "msgpack_catfact",
            MsgpackResponse(
                {
                    "fact": "test msgpack",
                    "length": 4,
                    "created_at": datetime(2025, 1, 4, 12, 15),
                    "colors": ["white", "yellow"],
                },
            ),
        )
        yield service


@pytest.fixture
def catfact_url(catfact_service: MockService) -> URL:
    return catfact_service.url
