"""In-process forwarding HTTP proxy for tests.

`start_proxy` spins up a real forward proxy (via aiohttp's ``RawTestServer``)
that records every request passing through it and forwards it to the absolute
target URL the client requested.  Combined with :func:`start_service` it lets
you test that a client genuinely routes through a proxy::

    async with start_service([MockRoute("GET", "/x", "ok")]) as target:
        target.register("ok", JsonResponse({"ok": True}))
        async with start_proxy() as proxy:
            async with ClientSession() as s:
                resp = await s.get(target.url / "x", proxy=proxy.url)
            proxy.assert_called(times=1, method="GET")

Only plain HTTP targets are supported (no ``CONNECT`` / HTTPS tunnelling).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from http import HTTPStatus

from aiohttp import BasicAuth, ClientSession
from aiohttp.test_utils import RawTestServer
from aiohttp.web_request import BaseRequest
from aiohttp.web_response import Response
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from asyncly.srvmocker.assertions import call_matches
from asyncly.srvmocker.models import RequestHistory

# Hop-by-hop headers must not be forwarded end-to-end (RFC 9110 section 7.6.1),
# plus the proxy-specific ones.
_HOP_BY_HOP = frozenset(
    h.lower()
    for h in (
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "host",
    )
)
# On the response we additionally drop Content-Length so aiohttp recomputes it
# from the (verbatim) body we relay.
_HOP_BY_HOP_RESPONSE = _HOP_BY_HOP | frozenset({"content-length"})


@dataclass(frozen=True)
class MockProxyService:
    """Handle to a running mock forwarding proxy.

    Returned by [`start_proxy`][asyncly.srvmocker.start_proxy]. Point a client at
    it via ``proxy=proxy.url`` and assert on the requests that passed through.
    The ``history`` holds every request the proxy received.
    """

    url: URL
    history: list[RequestHistory] = field(default_factory=list)

    def set_url(self, url: URL) -> None:
        object.__setattr__(self, "url", url)

    def get_calls(self) -> list[RequestHistory]:
        return list(self.history)

    def last_call(self) -> RequestHistory:
        if not self.history:
            raise AssertionError("no requests recorded by proxy")
        return self.history[-1]

    def assert_called(
        self,
        *,
        times: int | None = None,
        target: URL | str | None = None,
        method: str | None = None,
        json: object = None,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> None:
        """Assert that a matching request passed through the proxy.

        Like `MockService.assert_called`, plus two proxy-specific predicates:

        Args:
            times: If given, the exact number of forwarded requests expected.
            target: Expected absolute destination URL the client asked for.
            method: Expected HTTP method.
            json: Expected parsed JSON body (exact match).
            body: Expected raw body bytes (exact match).
            headers: Header key/values that must all be present (e.g.
                ``Proxy-Authorization``).
            query: Query key/values that must all be present.

        Raises:
            AssertionError: If no recorded request satisfies the criteria.
        """
        calls = self.get_calls()
        if times is not None and len(calls) != times:
            raise AssertionError(f"proxy: expected {times} call(s), got {len(calls)}")
        criteria = (target, method, json, body, headers, query)
        if times is not None and all(v is None for v in criteria):
            return
        if not calls:
            raise AssertionError("proxy: expected at least one call, got 0")
        for call in calls:
            if target is not None and str(call.request.url) != str(URL(target)):
                continue
            if method is not None and call.request.method != method:
                continue
            if call_matches(call, json=json, body=body, headers=headers, query=query):
                return
        raise AssertionError(
            f"proxy: none of {len(calls)} call(s) matched the given criteria"
        )

    def assert_not_called(self) -> None:
        if self.history:
            raise AssertionError(f"proxy: expected no calls, got {len(self.history)}")


def _relay_headers(
    source: CIMultiDictProxy[str], *, drop: frozenset[str]
) -> CIMultiDict[str]:
    """Copy headers preserving duplicates (e.g. multiple ``Set-Cookie``)."""
    relayed: CIMultiDict[str] = CIMultiDict()
    for key, value in source.items():
        if key.lower() not in drop:
            relayed.add(key, value)
    return relayed


@asynccontextmanager
async def start_proxy(
    *,
    auth: BasicAuth | None = None,
) -> AsyncGenerator[MockProxyService, None]:
    """Start an in-process forwarding HTTP proxy for tests.

    An async context manager. It records every request that passes through and
    forwards it to the absolute target the client requested (typically another
    [`start_service`][asyncly.srvmocker.start_service]), relaying the response
    verbatim. Only plain HTTP targets are supported (no ``CONNECT`` tunnelling).

    Args:
        auth: If given, require a matching ``Proxy-Authorization`` header.
            Requests without it (or with wrong credentials) get a
            ``407 Proxy Authentication Required`` and are not forwarded.

    Yields:
        MockProxyService: Handle exposing the proxy ``url`` and request history.
    """
    proxy = MockProxyService(url=URL())
    expected_auth = auth.encode() if auth is not None else None

    # Relay target responses verbatim (HTTP, uncompressed): keep the body and
    # its Content-Encoding untouched instead of auto-decompressing.
    forward_session = ClientSession(auto_decompress=False)

    async def _handler(request: BaseRequest) -> Response:
        body = await request.read()
        proxy.history.append(RequestHistory(request=request, body=body))

        if expected_auth is not None:
            provided = request.headers.get("Proxy-Authorization")
            if provided != expected_auth:
                return Response(
                    status=HTTPStatus.PROXY_AUTHENTICATION_REQUIRED,
                    reason="Proxy Authentication Required",
                    headers={"Proxy-Authenticate": "Basic"},
                )

        async with forward_session.request(
            method=request.method,
            url=request.url,
            headers=_relay_headers(request.headers, drop=_HOP_BY_HOP),
            data=body or None,
            allow_redirects=False,
        ) as upstream:
            payload = await upstream.read()
            return Response(
                status=upstream.status,
                reason=upstream.reason,
                headers=_relay_headers(upstream.headers, drop=_HOP_BY_HOP_RESPONSE),
                body=payload,
            )

    server = RawTestServer(_handler)
    try:
        await server.start_server()
        proxy.set_url(server.make_url(""))
        yield proxy
    finally:
        await server.close()
        await forward_session.close()
