import json as _json
from typing import Any

from asyncly.srvmocker.models import RequestHistory


def call_matches(
    call: RequestHistory,
    *,
    json: Any = None,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
) -> bool:
    if not _matches_body(call, body):
        return False
    if not _matches_json(call, json):
        return False
    if not _matches_headers(call, headers):
        return False
    if not _matches_query(call, query):
        return False
    return True


def _matches_body(call: RequestHistory, body: bytes | None) -> bool:
    return body is None or call.body == body


def _matches_json(call: RequestHistory, json: Any) -> bool:
    if json is None:
        return True
    try:
        parsed = _json.loads(call.body)
    except _json.JSONDecodeError:
        return False
    return parsed == json


def _matches_headers(call: RequestHistory, headers: dict[str, str] | None) -> bool:
    if headers is None:
        return True
    for k, v in headers.items():
        if call.request.headers.get(k) != v:
            return False
    return True


def _matches_query(call: RequestHistory, query: dict[str, str] | None) -> bool:
    if query is None:
        return True
    for k, v in query.items():
        if call.request.query.get(k) != v:
            return False
    return True
