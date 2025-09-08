import asyncio
from http import HTTPStatus
from types import MappingProxyType

from aiohttp import ClientSession, hdrs
from pydantic import BaseModel

from asyncly import DEFAULT_TIMEOUT, BaseHttpClient, ResponseHandlersType
from asyncly.client.handlers.pydantic import parse_model
from asyncly.client.timeout import TimeoutType


class CatfactSchema(BaseModel):
    fact: str
    length: int


class CatfactClient(BaseHttpClient):
    RANDOM_CATFACT_HANDLERS: ResponseHandlersType = MappingProxyType(
        {
            HTTPStatus.OK: parse_model(CatfactSchema),
        }
    )

    async def fetch_random_cat_fact(
        self,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
    ) -> CatfactSchema:
        return await self._make_req(
            method=hdrs.METH_GET,
            url=self._url / "fact/json",
            handlers=self.RANDOM_CATFACT_HANDLERS,
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
