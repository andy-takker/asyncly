from collections.abc import AsyncIterator
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


class CatfactStruct(Struct):
    fact: str
    length: int


class CatfactClient(BaseHttpClient):
    PYDANTIC_SCHEMA_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_model(CatfactSchema),
        }
    )
    MSGSPEC_STRUCT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_struct(CatfactStruct),
        }
    )
    JSON_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_json(lambda data: data["fact"]),
        }
    )

    async def fetch_pydantic_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactSchema:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact",
            handlers=self.PYDANTIC_SCHEMA_HANDLERS,
            timeout=timeout,
        )

    async def fetch_msgspec_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactStruct:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact",
            handlers=self.MSGSPEC_STRUCT_HANDLERS,
            timeout=timeout,
        )

    async def fetch_json_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> str:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact",
            handlers=self.JSON_HANDLERS,
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
