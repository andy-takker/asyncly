from collections.abc import AsyncIterator

import pytest
from yarl import URL

from asyncly.srvmocker.models import MockRoute, MockService
from asyncly.srvmocker.responses import JsonResponse
from asyncly.srvmocker.service import start_service


@pytest.fixture
async def catfact_service() -> AsyncIterator[MockService]:
    routes = [
        MockRoute("GET", "/fact", "random_catfact"),
    ]
    async with start_service(routes) as service:
        service.register(
            "random_catfact",
            JsonResponse({"fact": "test", "length": 4}),
        )
        yield service


@pytest.fixture
def catfact_url(catfact_service: MockService) -> URL:
    return catfact_service.url
