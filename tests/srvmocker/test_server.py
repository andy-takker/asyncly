from asyncly.srvmocker.models import MockRoute
from asyncly.srvmocker.responses.json import JsonResponse
from asyncly.srvmocker.service import start_service


async def test_create_empty_server():
    async with start_service([]) as service:
        assert service


async def test_create_server_with_routes():
    routes = [
        MockRoute("GET", "/fact", "random_catfact"),
    ]
    async with start_service(routes) as service:
        assert service


async def test_create_server_with_multiple_routes():
    routes = [
        MockRoute("GET", "/fact", "random_catfact"),
        MockRoute("GET", "/another", "another_catfact"),
    ]
    async with start_service(routes) as service:
        assert service


async def test_register_handler():
    routes = [
        MockRoute("GET", "/fact", "random_catfact"),
    ]
    async with start_service(routes) as service:
        service.register(
            "random_catfact",
            JsonResponse({"fact": "test", "length": 4}),
        )
        assert service.handlers["random_catfact"]
