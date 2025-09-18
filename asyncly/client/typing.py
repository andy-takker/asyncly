import sys
from collections.abc import Callable, Mapping
from datetime import timedelta
from http import HTTPStatus
from typing import Literal

from aiohttp import ClientTimeout
from yarl import URL

ResponseHandler = Callable
ResponseHandlersType = Mapping[HTTPStatus | int | str, ResponseHandler]

TimeoutType = ClientTimeout | timedelta | int | float
RouteResolver = Callable[[URL], str]

if sys.version_info >= (3, 11):
    from http import HTTPMethod

    MethodType = HTTPMethod | Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"]
else:
    MethodType = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"]
