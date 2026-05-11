import json as _json
from dataclasses import dataclass
from typing import Any

from aiohttp.web_request import Request


@dataclass(frozen=True)
class Match:
    """Request matcher attached to a MockRoute.

    json: parsed JSON body must equal this value exactly.
    body: raw body bytes must equal this value exactly.
    headers: every (key, value) here must be present in request headers (subset).
    query: every (key, value) here must be present in request query (subset).

    Match is value-immutable: `headers` and `query` dicts are defensively
    copied at construction so caller-side mutation cannot affect matcher
    behavior. The instances themselves remain unhashable due to dict
    fields -- wrap in a tuple of items if you need hashability.
    """

    json: Any = None
    body: bytes | None = None
    headers: dict[str, str] | None = None
    query: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.headers is not None:
            object.__setattr__(self, "headers", dict(self.headers))
        if self.query is not None:
            object.__setattr__(self, "query", dict(self.query))

    def matches(self, request: Request, body: bytes) -> bool:
        if not self._matches_body(body):
            return False
        if not self._matches_json(body):
            return False
        if not self._matches_headers(request):
            return False
        if not self._matches_query(request):
            return False
        return True

    def _matches_body(self, body: bytes) -> bool:
        return self.body is None or body == self.body

    def _matches_json(self, body: bytes) -> bool:
        if self.json is None:
            return True
        try:
            parsed = _json.loads(body)
        except _json.JSONDecodeError:
            return False
        return parsed == self.json

    def _matches_headers(self, request: Request) -> bool:
        if self.headers is None:
            return True
        for k, v in self.headers.items():
            if request.headers.get(k) != v:
                return False
        return True

    def _matches_query(self, request: Request) -> bool:
        if self.query is None:
            return True
        for k, v in self.query.items():
            if request.query.get(k) != v:
                return False
        return True
