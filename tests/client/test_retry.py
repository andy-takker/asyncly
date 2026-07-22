import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from http import HTTPStatus

import pytest
from aiohttp import ClientConnectionError
from yarl import URL

import asyncly
from asyncly import RetryContext, RetryEvent, RetryPolicy


def _context(
    *,
    method: str = "GET",
    attempt: int = 1,
    max_attempts: int = 3,
    replayable: bool = True,
    response_status: int | None = None,
    exception: BaseException | None = None,
) -> RetryContext:
    return RetryContext(
        method=method,
        url=URL("https://example.test/items"),
        attempt=attempt,
        max_attempts=max_attempts,
        replayable=replayable,
        response_status=response_status,
        exception=exception,
    )


def test_retry_api_is_public() -> None:
    assert asyncly.RetryPolicy
    assert asyncly.RetryContext
    assert asyncly.RetryEvent


def test_safe_defaults_retry_transient_status_for_idempotent_method() -> None:
    policy = RetryPolicy()

    assert policy.should_retry(_context(response_status=HTTPStatus.SERVICE_UNAVAILABLE))


def test_safe_defaults_include_trace_as_idempotent() -> None:
    policy = RetryPolicy()

    assert policy.should_retry(
        _context(method="TRACE", response_status=HTTPStatus.SERVICE_UNAVAILABLE)
    )


def test_safe_defaults_do_not_retry_unsafe_method() -> None:
    policy = RetryPolicy()

    assert not policy.should_retry(
        _context(method="POST", response_status=HTTPStatus.SERVICE_UNAVAILABLE)
    )


def test_safe_defaults_retry_connection_error() -> None:
    policy = RetryPolicy()

    assert policy.should_retry(_context(exception=ClientConnectionError("closed")))


def test_cancellation_is_never_retryable() -> None:
    policy = RetryPolicy(exceptions=(BaseException,))

    assert not policy.should_retry(_context(exception=asyncio.CancelledError()))


def test_non_replayable_body_suppresses_retry() -> None:
    policy = RetryPolicy()

    assert not policy.should_retry(
        _context(
            response_status=HTTPStatus.SERVICE_UNAVAILABLE,
            replayable=False,
        )
    )


def test_attempt_budget_is_enforced() -> None:
    policy = RetryPolicy(max_attempts=2)

    assert not policy.should_retry(
        _context(
            attempt=2,
            max_attempts=2,
            response_status=HTTPStatus.SERVICE_UNAVAILABLE,
        )
    )


def test_policy_accepts_custom_filters() -> None:
    policy = RetryPolicy(
        statuses={HTTPStatus.CONFLICT},
        exceptions=(ValueError,),
        methods={"POST"},
    )

    assert policy.should_retry(
        _context(method="POST", response_status=HTTPStatus.CONFLICT)
    )
    assert policy.should_retry(_context(method="POST", exception=ValueError()))
    assert not policy.should_retry(_context(response_status=HTTPStatus.CONFLICT))


def test_policy_defensively_freezes_collections() -> None:
    statuses = {HTTPStatus.SERVICE_UNAVAILABLE}
    methods = {"get"}
    policy = RetryPolicy(statuses=statuses, methods=methods)

    statuses.add(HTTPStatus.GATEWAY_TIMEOUT)
    methods.add("post")

    assert policy.statuses == frozenset({HTTPStatus.SERVICE_UNAVAILABLE})
    assert policy.methods == frozenset({"GET"})
    with pytest.raises(FrozenInstanceError):
        policy.max_attempts = 4  # type: ignore[misc]


def test_policy_rejects_invalid_attempt_limit() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)


def test_retry_after_delta_seconds_overrides_backoff() -> None:
    policy = RetryPolicy(backoff=lambda context: 99.0)

    assert (
        policy.get_delay(
            _context(response_status=HTTPStatus.SERVICE_UNAVAILABLE),
            retry_after="7",
        )
        == 7.0
    )


def test_retry_after_http_date_overrides_backoff() -> None:
    policy = RetryPolicy(backoff=lambda context: 99.0)
    now = datetime(2015, 10, 21, 7, 27, tzinfo=timezone.utc)

    delay = policy.get_delay(
        _context(response_status=HTTPStatus.SERVICE_UNAVAILABLE),
        retry_after="Wed, 21 Oct 2015 07:28:00 GMT",
        now=now,
    )

    assert delay == 60.0


def test_invalid_retry_after_falls_back_to_strategy() -> None:
    policy = RetryPolicy(backoff=lambda context: context.attempt * 0.25)

    delay = policy.get_delay(
        _context(
            attempt=2,
            response_status=HTTPStatus.SERVICE_UNAVAILABLE,
        ),
        retry_after="later",
    )

    assert delay == 0.5


def test_negative_backoff_is_rejected() -> None:
    policy = RetryPolicy(backoff=lambda context: -1.0)

    with pytest.raises(ValueError, match="non-negative"):
        policy.get_delay(_context(response_status=HTTPStatus.SERVICE_UNAVAILABLE))


def test_retry_event_is_immutable() -> None:
    event = RetryEvent(
        kind="scheduled",
        context=_context(response_status=HTTPStatus.SERVICE_UNAVAILABLE),
        delay=0.5,
        reason="status",
    )

    with pytest.raises(FrozenInstanceError):
        event.delay = 1.0  # type: ignore[misc]
