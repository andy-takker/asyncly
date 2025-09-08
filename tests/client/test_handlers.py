from datetime import datetime

from tests.plugins.client import CatfactClient, CatfactSchema, CatfactStruct


async def test_parse_pydantic_schema(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_pydantic_cat_fact()
    assert fact == CatfactSchema(
        fact="test json",
        length=1,
        created_at=datetime(2025, 1, 1, 12, 15),
        colors=["red", "blue"],
    )


async def test_parse_json(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_json_cat_fact()
    assert fact == "test json"


async def test_parse_json_msgspec_schema(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_json_msgspec_cat_fact()
    assert fact == CatfactStruct(
        fact="test json",
        length=1,
        created_at=datetime(2025, 1, 1, 12, 15),
        colors=["red", "blue"],
    )


async def test_parse_toml_msgspec_schema(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_toml_cat_fact()
    assert fact == CatfactStruct(
        fact="test toml",
        length=2,
        created_at=datetime(2025, 1, 2, 12, 15),
        colors=["orange", "blue"],
    )


async def test_parse_yaml_msgspec_schema(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_yaml_cat_fact()
    assert fact == CatfactStruct(
        fact="test yaml",
        length=3,
        created_at=datetime(2025, 1, 3, 12, 15),
        colors=["red", "black"],
    )


async def test_parse_msgpack_msgspec_schema(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_msgpack_cat_fact()
    assert fact == CatfactStruct(
        fact="test msgpack",
        length=4,
        created_at=datetime(2025, 1, 4, 12, 15),
        colors=["white", "yellow"],
    )
