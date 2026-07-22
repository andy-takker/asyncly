from http import HTTPStatus
from typing import Any

import pytest
from aiohttp import ClientResponse

from asyncly import RetryPolicy
from asyncly.srvmocker import DisconnectResponse, RawResponse, SequenceResponse
from asyncly.srvmocker.models import MockService
from asyncly.srvmocker.responses.content import ContentResponse
from tests.plugins.instrumented_client import InstrumetedCatfactClient


class LifecycleLessSink:
    """A sink implementing only ``observe_request`` (no lifecycle hooks).

    Uses ``**kwargs`` so it tolerates the current ``observe_request`` contract;
    it exists to prove the client does NOT require the optional lifecycle hooks.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def observe_request(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class OldSignatureSink:
    """A sink pinned to the pre-0.8 ``observe_request`` signature.

    It does NOT declare ``operation``/``outcome`` — the two params added in this
    release. Kept to document that the signature change is a deliberate break for
    sink authors, not an accident.
    """

    def observe_request(
        self,
        *,
        client: str,
        method: str,
        route: str,
        status: int | str,
        duration_seconds: float,
        error_type: str | None = None,
    ) -> None:
        return


class SpySink(LifecycleLessSink):
    """A modern sink recording in-flight balance."""

    def __init__(self) -> None:
        super().__init__()
        self.in_flight = 0
        self.max_in_flight = 0
        self.starts = 0
        self.ends = 0

    def on_request_start(self, **kwargs: Any) -> None:
        self.starts += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)

    def on_request_end(self, **kwargs: Any) -> None:
        self.ends += 1
        self.in_flight -= 1


async def test_sink_without_lifecycle_hooks_still_receives_observe_request(
    instrumented_client: InstrumetedCatfactClient,
) -> None:
    sink = LifecycleLessSink()
    with instrumented_client.instrument(sink) as client:
        assert client._sink_has_lifecycle is False
        await client.fetch_pydantic_cat_fact()

    assert len(sink.calls) == 1
    assert sink.calls[0]["status"] == HTTPStatus.OK
    assert sink.calls[0]["outcome"] == "response"
    assert sink.calls[0]["operation"] == "get_pydantic_cat_fact"


async def test_old_observe_request_signature_is_a_deliberate_break(
    instrumented_client: InstrumetedCatfactClient,
) -> None:
    # Documents the breaking change: a sink pinned to the old signature raises
    # because the client now passes operation=/outcome=.
    sink = OldSignatureSink()
    with instrumented_client.instrument(sink) as client:
        with pytest.raises(TypeError, match="operation|outcome"):
            await client.fetch_pydantic_cat_fact()


async def test_lifecycle_sink_detected_and_balanced(
    instrumented_client: InstrumetedCatfactClient,
) -> None:
    sink = SpySink()
    with instrumented_client.instrument(sink) as client:
        assert client._sink_has_lifecycle is True
        await client.fetch_pydantic_cat_fact()

    assert sink.starts == 1
    assert sink.ends == 1
    assert sink.in_flight == 0
    assert sink.max_in_flight == 1


async def test_in_flight_decremented_on_error(
    instrumented_client: InstrumetedCatfactClient,
    catfact_service: MockService,
) -> None:
    catfact_service.register(
        "json_catfact",
        ContentResponse(status=HTTPStatus.INTERNAL_SERVER_ERROR),
    )
    sink = SpySink()
    with instrumented_client.instrument(sink) as client:
        try:
            await client.fetch_pydantic_cat_fact()
        except Exception:  # noqa: BLE001
            pass

    # dec runs in finally even when handling raised
    assert sink.starts == 1
    assert sink.ends == 1
    assert sink.in_flight == 0
    assert sink.calls[0]["outcome"] == "response"
    assert sink.calls[0]["error_type"] == "invalid_response"
    assert sink.calls[0]["status"] == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_each_retry_attempt_is_observed_as_a_physical_request(
    instrumented_client: InstrumetedCatfactClient,
    catfact_service: MockService,
) -> None:
    async def read_body(response: ClientResponse) -> bytes:
        return await response.read()

    catfact_service.register(
        "json_catfact",
        SequenceResponse(
            [
                RawResponse(status=HTTPStatus.SERVICE_UNAVAILABLE),
                RawResponse(body=b"ok", status=HTTPStatus.OK),
            ]
        ),
    )
    sink = SpySink()

    with instrumented_client.instrument(sink) as client:
        result = await client._make_req(
            method="GET",
            url=client.url / "fact/json",
            handlers={"*": read_body},
            retry=RetryPolicy(backoff=lambda context: 0.0),
            operation="retrying_fact",
        )

    assert result == b"ok"
    assert [call["status"] for call in sink.calls] == [
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.OK,
    ]
    assert [call["operation"] for call in sink.calls] == [
        "retrying_fact",
        "retrying_fact",
    ]
    assert sink.starts == 2
    assert sink.ends == 2


async def test_retry_transport_failure_keeps_specific_error_type(
    instrumented_client: InstrumetedCatfactClient,
    catfact_service: MockService,
) -> None:
    async def read_body(response: ClientResponse) -> bytes:
        return await response.read()

    catfact_service.register(
        "json_catfact",
        SequenceResponse(
            [
                DisconnectResponse(),
                RawResponse(body=b"ok", status=HTTPStatus.OK),
            ]
        ),
    )
    sink = SpySink()

    with instrumented_client.instrument(sink) as client:
        result = await client._make_req(
            method="GET",
            url=client.url / "fact/json",
            handlers={"*": read_body},
            retry=RetryPolicy(backoff=lambda context: 0.0),
            operation="retrying_fact",
        )

    assert result == b"ok"
    assert [call["status"] for call in sink.calls] == ["none", HTTPStatus.OK]
    assert [call["outcome"] for call in sink.calls] == [
        "network_error",
        "response",
    ]
    assert [call["error_type"] for call in sink.calls] == [
        "server_disconnected",
        None,
    ]
