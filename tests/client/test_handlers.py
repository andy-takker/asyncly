from tests.plugins.client import CatfactClient, CatfactSchema, CatfactStruct


async def test_parse_pydantic_schema(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_pydantic_cat_fact()
    assert fact == CatfactSchema(fact="test", length=4)


async def test_parse_msgspec_schema(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_msgspec_cat_fact()
    assert fact == CatfactStruct(fact="test", length=4)


async def test_parse_json(catfact_client: CatfactClient) -> None:
    fact = await catfact_client.fetch_json_cat_fact()
    assert fact == "test"
