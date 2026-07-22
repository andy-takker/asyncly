import asyncio
from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any

import pytest
from aiohttp import (
    ClientConnectionError,
    ClientPayloadError,
    ClientResponse,
    ClientSession,
)

from asyncly import BaseHttpClient, RetryEvent, RetryPolicy
from asyncly.srvmocker import (
    DisconnectResponse,
    LatencyResponse,
    MockRoute,
    RawResponse,
    SequenceResponse,
    TruncatedResponse,
    start_service,
)


async def _read_response(response: ClientResponse) -> tuple[int, bytes]:
    return response.status, await response.read()


async def _request(
    service_url: Any,
    *,
    method: str = "GET",
    retry: RetryPolicy,
    observer: Any = None,
    **kwargs: Any,
) -> tuple[int, bytes]:
    async with ClientSession() as session:
        client = BaseHttpClient(
            url=service_url,
            session=session,
            client_name="retry-test",
        )
        return await client._make_req(
            method=method,
            url=service_url / "resource",
            handlers={"*": _read_response},
            retry=retry,
            retry_observer=observer,
            **kwargs,
        )


async def test_retries_retryable_status_before_running_handler() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]
    handled: list[int] = []

    async def handler(response: ClientResponse) -> bytes:
        handled.append(response.status)
        return await response.read()

    async with start_service(routes) as service:
        service.register(
            "resource",
            SequenceResponse(
                [
                    RawResponse(status=HTTPStatus.SERVICE_UNAVAILABLE),
                    RawResponse(body=b"ok", status=HTTPStatus.OK),
                ]
            ),
        )
        async with ClientSession() as session:
            client = BaseHttpClient(service.url, session, "retry-test")
            result = await client._make_req(
                method="GET",
                url=service.url / "resource",
                handlers={"*": handler},
                retry=RetryPolicy(backoff=lambda context: 0.0),
            )

        assert result == b"ok"
        assert handled == [HTTPStatus.OK]
        service.assert_called("resource", times=2)


async def test_observer_receives_scheduled_event() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]
    events: list[RetryEvent] = []

    async with start_service(routes) as service:
        service.register(
            "resource",
            SequenceResponse(
                [
                    RawResponse(status=HTTPStatus.SERVICE_UNAVAILABLE),
                    RawResponse(status=HTTPStatus.OK),
                ]
            ),
        )
        await _request(
            service.url,
            retry=RetryPolicy(backoff=lambda context: 0.25),
            observer=events.append,
        )

    assert [(event.kind, event.reason, event.delay) for event in events] == [
        ("scheduled", "status", 0.25)
    ]
    assert events[0].context.response_status == HTTPStatus.SERVICE_UNAVAILABLE
    assert events[0].context.attempt == 1


async def test_last_retryable_response_runs_handler_and_emits_exhausted() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]
    events: list[RetryEvent] = []

    async with start_service(routes) as service:
        service.register(
            "resource",
            RawResponse(
                body=b"unavailable",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            ),
        )
        result = await _request(
            service.url,
            retry=RetryPolicy(
                max_attempts=2,
                backoff=lambda context: 0.0,
            ),
            observer=events.append,
        )

        assert result == (HTTPStatus.SERVICE_UNAVAILABLE, b"unavailable")
        service.assert_called("resource", times=2)

    assert [event.kind for event in events] == ["scheduled", "exhausted"]
    assert events[-1].reason == "attempts_exhausted"
    assert events[-1].context.attempt == 2


async def test_retryable_status_on_unsafe_method_is_suppressed() -> None:
    routes = [MockRoute("POST", "/resource", "resource")]
    events: list[RetryEvent] = []

    async with start_service(routes) as service:
        service.register(
            "resource",
            RawResponse(status=HTTPStatus.SERVICE_UNAVAILABLE),
        )
        result = await _request(
            service.url,
            method="POST",
            retry=RetryPolicy(backoff=lambda context: 0.0),
            observer=events.append,
            json={"value": 1},
        )

        assert result == (HTTPStatus.SERVICE_UNAVAILABLE, b"")
        service.assert_called("resource", times=1)

    assert [event.kind for event in events] == ["suppressed"]
    assert events[0].reason == "method_not_allowed"


async def test_replayable_form_body_is_sent_again() -> None:
    routes = [MockRoute("POST", "/resource", "resource")]

    async with start_service(routes) as service:
        service.register(
            "resource",
            SequenceResponse(
                [
                    RawResponse(status=HTTPStatus.SERVICE_UNAVAILABLE),
                    RawResponse(status=HTTPStatus.OK),
                ]
            ),
        )
        result = await _request(
            service.url,
            method="POST",
            retry=RetryPolicy(
                methods={"POST"},
                backoff=lambda context: 0.0,
            ),
            data={"value": "one"},
        )

        assert result == (HTTPStatus.OK, b"")
        calls = service.get_calls("resource")
        assert [call.body for call in calls] == [b"value=one", b"value=one"]


async def test_streaming_body_suppresses_retry() -> None:
    routes = [MockRoute("POST", "/resource", "resource")]
    events: list[RetryEvent] = []

    async def body() -> AsyncIterator[bytes]:
        yield b"streamed"

    async with start_service(routes) as service:
        service.register(
            "resource",
            RawResponse(status=HTTPStatus.SERVICE_UNAVAILABLE),
        )
        result = await _request(
            service.url,
            method="POST",
            retry=RetryPolicy(
                methods={"POST"},
                backoff=lambda context: 0.0,
            ),
            observer=events.append,
            data=body(),
        )

        assert result == (HTTPStatus.SERVICE_UNAVAILABLE, b"")
        service.assert_called("resource", times=1)

    assert [event.kind for event in events] == ["suppressed"]
    assert events[0].reason == "body_not_replayable"


async def test_retry_after_header_controls_scheduled_delay() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]
    events: list[RetryEvent] = []

    async with start_service(routes) as service:
        service.register(
            "resource",
            SequenceResponse(
                [
                    RawResponse(
                        status=HTTPStatus.TOO_MANY_REQUESTS,
                        headers={"Retry-After": "0"},
                    ),
                    RawResponse(status=HTTPStatus.OK),
                ]
            ),
        )
        result = await _request(
            service.url,
            retry=RetryPolicy(backoff=lambda context: 99.0),
            observer=events.append,
        )

        assert result == (HTTPStatus.OK, b"")
        service.assert_called("resource", times=2)

    assert [(event.kind, event.delay) for event in events] == [("scheduled", 0.0)]


async def test_disconnect_before_headers_is_retried() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]
    events: list[RetryEvent] = []

    async with start_service(routes) as service:
        service.register(
            "resource",
            SequenceResponse([DisconnectResponse(), RawResponse(body=b"ok")]),
        )
        result = await _request(
            service.url,
            retry=RetryPolicy(backoff=lambda context: 0.0),
            observer=events.append,
        )

        assert result == (HTTPStatus.OK, b"ok")
        service.assert_called("resource", times=2)

    assert [(event.kind, event.reason) for event in events] == [
        ("scheduled", "exception")
    ]


async def test_unmatched_disconnect_raises_original_aiohttp_exception() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]

    async with start_service(routes) as service:
        service.register("resource", DisconnectResponse())

        with pytest.raises(ClientConnectionError):
            await _request(
                service.url,
                retry=RetryPolicy(
                    exceptions=(ValueError,),
                    backoff=lambda context: 0.0,
                ),
            )

        service.assert_called("resource", times=1)


async def test_truncated_body_is_retried() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]

    async with start_service(routes) as service:
        service.register(
            "resource",
            SequenceResponse(
                [TruncatedResponse(body=b"partial"), RawResponse(body=b"complete")]
            ),
        )
        result = await _request(
            service.url,
            retry=RetryPolicy(backoff=lambda context: 0.0),
        )

        assert result == (HTTPStatus.OK, b"complete")
        service.assert_called("resource", times=2)


async def test_last_transport_exception_is_re_raised_without_wrapper() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]
    events: list[RetryEvent] = []

    async with start_service(routes) as service:
        service.register("resource", TruncatedResponse(body=b"partial"))

        with pytest.raises(ClientPayloadError):
            await _request(
                service.url,
                retry=RetryPolicy(
                    max_attempts=2,
                    backoff=lambda context: 0.0,
                ),
                observer=events.append,
            )

        service.assert_called("resource", times=2)

    assert [event.kind for event in events] == ["scheduled", "exhausted"]
    assert events[-1].reason == "attempts_exhausted"


async def test_cancellation_is_not_retried() -> None:
    routes = [MockRoute("GET", "/resource", "resource")]
    events: list[RetryEvent] = []

    async with start_service(routes) as service:
        service.register(
            "resource",
            LatencyResponse(RawResponse(), latency=1.0),
        )
        async with ClientSession() as session:
            client = BaseHttpClient(service.url, session, "retry-test")
            task = asyncio.create_task(
                client._make_req(
                    method="GET",
                    url=service.url / "resource",
                    handlers={"*": _read_response},
                    retry=RetryPolicy(backoff=lambda context: 0.0),
                    retry_observer=events.append,
                )
            )
            while not service.get_calls("resource"):
                await asyncio.sleep(0)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

        service.assert_called("resource", times=1)

    assert events == []


async def test_one_policy_can_be_shared_by_concurrent_requests() -> None:
    routes = [
        MockRoute("GET", "/one", "one"),
        MockRoute("GET", "/two", "two"),
    ]
    policy = RetryPolicy(backoff=lambda context: 0.0)

    async with start_service(routes) as service:
        service.register(
            "one",
            SequenceResponse(
                [
                    RawResponse(status=HTTPStatus.SERVICE_UNAVAILABLE),
                    RawResponse(body=b"one"),
                ]
            ),
        )
        service.register(
            "two",
            SequenceResponse(
                [
                    RawResponse(status=HTTPStatus.SERVICE_UNAVAILABLE),
                    RawResponse(body=b"two"),
                ]
            ),
        )
        async with ClientSession() as session:
            client = BaseHttpClient(service.url, session, "retry-test")
            one, two = await asyncio.gather(
                client._make_req(
                    method="GET",
                    url=service.url / "one",
                    handlers={"*": _read_response},
                    retry=policy,
                ),
                client._make_req(
                    method="GET",
                    url=service.url / "two",
                    handlers={"*": _read_response},
                    retry=policy,
                ),
            )

        assert one == (HTTPStatus.OK, b"one")
        assert two == (HTTPStatus.OK, b"two")
        service.assert_called("one", times=2)
        service.assert_called("two", times=2)
