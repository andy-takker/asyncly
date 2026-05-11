from collections.abc import MutableMapping, MutableSequence
from dataclasses import dataclass

from aiohttp.web_request import Request
from yarl import URL

from asyncly.srvmocker.matching import Match
from asyncly.srvmocker.responses.base import BaseMockResponse


@dataclass(frozen=True)
class MockRoute:
    method: str
    path: str
    handler_name: str
    match: Match | None = None


@dataclass
class RequestHistory:
    request: Request
    body: bytes


@dataclass(frozen=True)
class MockService:
    history: MutableSequence[RequestHistory]
    history_map: MutableMapping[str, MutableSequence[RequestHistory]]
    url: URL
    handlers: MutableMapping[str, BaseMockResponse]
    _handler_names: frozenset[str] = frozenset()

    def register(self, name: str, resp: BaseMockResponse) -> None:
        if self._handler_names and name not in self._handler_names:
            import warnings

            warnings.warn(
                f"register() called with unknown handler_name {name!r}; "
                f"declared handlers: {sorted(self._handler_names)}. "
                "This will raise UnknownHandlerError in asyncly 0.7.",
                DeprecationWarning,
                stacklevel=2,
            )
        self.handlers[name] = resp

    def set_url(self, url: URL) -> None:
        object.__setattr__(self, "url", url)
