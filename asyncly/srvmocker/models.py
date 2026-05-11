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

    def get_calls(self, name: str) -> list[RequestHistory]:
        return list(self.history_map.get(name, []))

    def last_call(self, name: str) -> RequestHistory:
        calls = self.history_map.get(name) or []
        if not calls:
            raise AssertionError(f"no calls recorded for handler {name!r}")
        return calls[-1]

    def assert_called(
        self,
        name: str,
        *,
        times: int | None = None,
        json: object = None,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> None:
        from asyncly.srvmocker.assertions import call_matches

        calls = self.get_calls(name)
        if times is not None:
            if len(calls) != times:
                raise AssertionError(
                    f"handler {name!r}: expected {times} call(s), got {len(calls)}"
                )
            if all(v is None for v in (json, body, headers, query)):
                return
        if not calls:
            raise AssertionError(f"handler {name!r}: expected at least one call, got 0")
        for call in calls:
            if call_matches(call, json=json, body=body, headers=headers, query=query):
                return
        raise AssertionError(
            f"handler {name!r}: none of {len(calls)} call(s) matched the given criteria"
        )

    def assert_not_called(self, name: str) -> None:
        calls = self.get_calls(name)
        if calls:
            raise AssertionError(
                f"handler {name!r}: expected no calls, got {len(calls)}"
            )
