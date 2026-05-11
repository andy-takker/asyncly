import warnings

import pytest

from asyncly.srvmocker import JsonResponse, MockRoute, start_service


async def test_register_unknown_name_emits_deprecation_warning() -> None:
    routes = [MockRoute("GET", "/x", "known")]
    async with start_service(routes) as service:
        with pytest.warns(DeprecationWarning, match="unknown handler_name"):
            service.register("typo", JsonResponse({}))


async def test_register_known_name_emits_no_warning() -> None:
    routes = [MockRoute("GET", "/x", "known")]
    async with start_service(routes) as service:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            service.register("known", JsonResponse({}))
