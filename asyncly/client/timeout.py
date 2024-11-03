from datetime import timedelta
from functools import singledispatch

from aiohttp import ClientTimeout

TimeoutType = ClientTimeout | timedelta | int | float


@singledispatch
def get_timeout(t: TimeoutType) -> ClientTimeout:
    raise TypeError(f"Unknown type {type(t)}")


@get_timeout.register(ClientTimeout)
def _client_timeout(t: ClientTimeout) -> ClientTimeout:
    return t


@get_timeout.register(timedelta)
def _timedelta(t: timedelta) -> ClientTimeout:
    return ClientTimeout(total=t.total_seconds())


@get_timeout.register(int)
@get_timeout.register(float)
def _number(t: int | float) -> ClientTimeout:
    return ClientTimeout(total=float(t))
