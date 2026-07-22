from collections.abc import Mapping, MutableMapping, MutableSequence
from dataclasses import dataclass
from types import MappingProxyType

from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy
from yarl import URL

from asyncly.srvmocker.exceptions import UnknownHandlerError
from asyncly.srvmocker.matching import Match
from asyncly.srvmocker.responses.base import BaseMockResponse


@dataclass(frozen=True)
class MockRoute:
    """Binds an HTTP method and path to a named handler.

    Attributes:
        method: HTTP method, e.g. ``"GET"``.
        path: URL path, e.g. ``"/items"``.
        handler_name: Label a response is registered under via
            `MockService.register`.
        match: Optional [`Match`][asyncly.srvmocker.Match]; when several routes
            share a ``(method, path)``, the first whose match succeeds wins. A
            route with no ``match`` is an always-matching fallback.
    """

    method: str
    path: str
    handler_name: str
    match: Match | None = None


@dataclass(frozen=True)
class RecordedRequest:
    """Immutable snapshot of a request received by the mock server.

    Attributes:
        method: HTTP method.
        url: Full request URL, including its query string.
        path: Request path without the query string.
        headers: Immutable case-insensitive headers snapshot.
        query: Immutable query parameters snapshot.
        path_params: Immutable route path parameters snapshot.
        body: The raw request body bytes.
        handler_name: Name of the selected route handler.
    """

    method: str
    url: URL
    path: str
    headers: Mapping[str, str]
    query: Mapping[str, str]
    path_params: Mapping[str, str]
    body: bytes
    handler_name: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "headers",
            CIMultiDictProxy(CIMultiDict(self.headers)),
        )
        object.__setattr__(
            self,
            "query",
            MultiDictProxy(MultiDict(self.query)),
        )
        object.__setattr__(
            self,
            "path_params",
            MappingProxyType(dict(self.path_params)),
        )
        object.__setattr__(self, "body", bytes(self.body))


# Deprecated compatibility name for 0.9; use RecordedRequest in new code.
RequestHistory = RecordedRequest


@dataclass(frozen=True)
class MockService:
    """Handle to a running mock server.

    Returned by [`start_service`][asyncly.srvmocker.start_service]. Use it to
    register responses, read the recorded request history, and assert on what a
    client sent. The ``url`` attribute is the base URL to point a client at.
    """

    history: MutableSequence[RecordedRequest]
    history_map: MutableMapping[str, MutableSequence[RecordedRequest]]
    url: URL
    handlers: MutableMapping[str, BaseMockResponse]
    _handler_names: frozenset[str] = frozenset()

    def register(self, name: str, resp: BaseMockResponse) -> None:
        """Register (or replace) the response returned for a handler name.

        Args:
            name: A ``handler_name`` declared on one of the routes.
            resp: The response to return. May be re-registered mid-test to
                change behavior.
        """
        if name not in self._handler_names:
            raise UnknownHandlerError(
                f"register() called with unknown handler_name {name!r}; "
                f"declared handlers: {sorted(self._handler_names)}"
            )
        self.handlers[name] = resp

    def set_url(self, url: URL) -> None:
        object.__setattr__(self, "url", url)

    def get_calls(self, name: str) -> list[RecordedRequest]:
        """Return all recorded calls for a handler, oldest first."""
        return list(self.history_map.get(name, []))

    def last_call(self, name: str) -> RecordedRequest:
        """Return the most recent call for a handler.

        Raises:
            AssertionError: If the handler recorded no calls.
        """
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
        """Assert that a matching request was received.

        With only ``times``, asserts the exact call count. With predicates,
        asserts at least one recorded call matched all of them: ``json`` and
        ``body`` match exactly, while ``headers`` and ``query`` match as a
        subset.

        Args:
            name: The handler name to check.
            times: If given, the exact number of calls expected.
            json: Expected parsed JSON body (exact match).
            body: Expected raw body bytes (exact match).
            headers: Header key/values that must all be present.
            query: Query key/values that must all be present.

        Raises:
            AssertionError: If no recorded call satisfies the criteria.
        """
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
        """Assert the handler received no requests.

        Raises:
            AssertionError: If any call was recorded for ``name``.
        """
        calls = self.get_calls(name)
        if calls:
            raise AssertionError(
                f"handler {name!r}: expected no calls, got {len(calls)}"
            )
