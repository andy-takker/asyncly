from asyncly.srvmocker.models import MockService
from tests.plugins.client import CatfactClient


async def test_history_length_called_once(
    catfact_service: MockService, catfact_client: CatfactClient
) -> None:
    await catfact_client.fetch_pydantic_cat_fact()
    assert len(catfact_service.history) == 1


async def test_history_called_several_times(
    catfact_service: MockService, catfact_client: CatfactClient
) -> None:
    for _ in range(3):
        await catfact_client.fetch_pydantic_cat_fact()
    assert len(catfact_service.history) == 3


async def test_history_map_called_once(
    catfact_service: MockService, catfact_client: CatfactClient
) -> None:
    await catfact_client.fetch_json_msgspec_cat_fact()
    assert len(catfact_service.history_map["json_catfact"]) == 1


async def test_history_map_called_several_times(
    catfact_service: MockService, catfact_client: CatfactClient
) -> None:
    await catfact_client.fetch_json_msgspec_cat_fact()
    await catfact_client.fetch_json_msgspec_cat_fact()
    await catfact_client.fetch_json_msgspec_cat_fact()
    assert len(catfact_service.history_map["json_catfact"]) == 3
