import asyncio
from http import HTTPStatus
from types import MappingProxyType

from aiohttp import ClientSession, hdrs
from msgspec import Struct
from pydantic import BaseModel

from asyncly import DEFAULT_TIMEOUT, BaseHttpClient, ResponseHandlersType
from asyncly.client.handlers.msgspec import parse_struct
from asyncly.client.handlers.pydantic import parse_model
from asyncly.client.timeout import TimeoutType


class CatfactModel(BaseModel):
    fact: str
    length: int


class CatfactStruct(Struct):
    fact: str
    length: int


class CatfactClient(BaseHttpClient):
    MODEL_CATFACT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_model(CatfactModel),
        }
    )
    MSGPACK_CATFACT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_struct(CatfactStruct, data_format="msgpack"),
        }
    )

    async def fetch_catfact_model(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactModel:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/json",
            handlers=self.MODEL_CATFACT_HANDLERS,
            timeout=timeout,
        )

    async def fetch_catfact_msgpack(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactStruct:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/msgpack",
            handlers=self.MSGPACK_CATFACT_HANDLERS,
            timeout=timeout,
        )


async def main() -> None:
    async with ClientSession() as session:
        client = CatfactClient(
            client_name="catfact",
            session=session,
            url="https://catfact.ninja",
        )
        fact = await client.fetch_random_cat_fact()
        print(fact)  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
