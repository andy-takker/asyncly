from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from http import HTTPStatus
from types import MappingProxyType

import pytest
from aiohttp import ClientSession, hdrs
from msgspec import Struct
from pydantic import BaseModel
from yarl import URL

from asyncly import DEFAULT_TIMEOUT, BaseHttpClient, ResponseHandlersType
from asyncly.client.handlers.json import parse_json
from asyncly.client.handlers.msgspec import parse_struct
from asyncly.client.handlers.pydantic import parse_model
from asyncly.client.timeout import TimeoutType


class CatfactSchema(BaseModel):
    fact: str
    length: int
    created_at: datetime
    colors: Sequence[str]


class CatfactStruct(Struct):
    fact: str
    length: int
    created_at: datetime
    colors: Sequence[str]


class CatfactClient(BaseHttpClient):
    PYDANTIC_SCHEMA_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            "*": parse_model(CatfactSchema),
        }
    )
    MSGSPEC_JSON_STRUCT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_struct(CatfactStruct),
        }
    )
    MSGSPEC_TOML_STRUCT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_struct(CatfactStruct, data_format="toml"),
        }
    )
    MSGSPEC_YAML_STRUCT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_struct(CatfactStruct, data_format="yaml"),
        }
    )
    MSGSPEC_MSGPACK_STRUCT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_struct(CatfactStruct, data_format="msgpack"),
        }
    )
    JSON_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            "2xx": parse_json(lambda data: data["fact"]),
        }
    )

    async def fetch_pydantic_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactSchema:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/json",
            handlers=self.PYDANTIC_SCHEMA_HANDLERS,
            timeout=timeout,
        )

    async def fetch_json_msgspec_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactStruct:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/json",
            handlers=self.MSGSPEC_JSON_STRUCT_HANDLERS,
            timeout=timeout,
        )

    async def fetch_json_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> str:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/json",
            handlers=self.JSON_HANDLERS,
            timeout=timeout,
        )

    async def fetch_toml_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactStruct:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/toml",
            handlers=self.MSGSPEC_TOML_STRUCT_HANDLERS,
            timeout=timeout,
        )

    async def fetch_yaml_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactStruct:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/yaml",
            handlers=self.MSGSPEC_YAML_STRUCT_HANDLERS,
            timeout=timeout,
        )

    async def fetch_msgpack_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactStruct:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/msgpack",
            handlers=self.MSGSPEC_MSGPACK_STRUCT_HANDLERS,
            timeout=timeout,
        )


@pytest.fixture
async def catfact_client(catfact_url: URL) -> AsyncIterator[CatfactClient]:
    async with ClientSession() as session:
        client = CatfactClient(
            client_name="catfact",
            session=session,
            url=catfact_url,
        )
        yield client
