import asyncio
import errno
import socket

import pytest
from aiohttp import (
    ClientConnectorCertificateError,
    ClientConnectorDNSError,
    ClientConnectorError,
    ClientConnectorSSLError,
    ClientOSError,
    ClientPayloadError,
    ConnectionTimeoutError,
    ServerDisconnectedError,
    ServerTimeoutError,
)
from aiohttp.client_reqrep import ConnectionKey

from asyncly.client.metrics import taxonomy
from asyncly.client.metrics.taxonomy import classify_exception

_KEY = ConnectionKey("example.com", 443, True, True, None, None, None)


def _dns_error() -> ClientConnectorDNSError:
    return ClientConnectorDNSError(_KEY, socket.gaierror(socket.EAI_NONAME, "name"))


def _ssl_error() -> ClientConnectorSSLError:
    return ClientConnectorSSLError(_KEY, OSError("handshake"))


def _cert_error() -> ClientConnectorCertificateError:
    return ClientConnectorCertificateError(_KEY, Exception("bad cert"))


def _connect_error() -> ClientConnectorError:
    return ClientConnectorError(_KEY, OSError(errno.ECONNREFUSED, "refused"))


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (asyncio.CancelledError(), (taxonomy.CANCELLED, taxonomy.NONE)),
        # ConnectionTimeoutError is a ServerTimeoutError subclass — must be
        # classified as a connect timeout, not read.
        (ConnectionTimeoutError(), (taxonomy.TIMEOUT, taxonomy.CONNECT_ERROR)),
        (ServerTimeoutError(), (taxonomy.TIMEOUT, taxonomy.READ_TIMEOUT)),
        (TimeoutError(), (taxonomy.TIMEOUT, taxonomy.READ_TIMEOUT)),
        (_ssl_error(), (taxonomy.NETWORK_ERROR, taxonomy.TLS_ERROR)),
        (_cert_error(), (taxonomy.NETWORK_ERROR, taxonomy.TLS_ERROR)),
        (_dns_error(), (taxonomy.NETWORK_ERROR, taxonomy.DNS_ERROR)),
        (_connect_error(), (taxonomy.NETWORK_ERROR, taxonomy.CONNECT_ERROR)),
        (
            ServerDisconnectedError(),
            (taxonomy.NETWORK_ERROR, taxonomy.SERVER_DISCONNECTED),
        ),
        (
            ClientOSError(errno.ECONNRESET, "reset"),
            (taxonomy.NETWORK_ERROR, taxonomy.CONNECTION_RESET),
        ),
        (
            ConnectionResetError("reset"),
            (taxonomy.NETWORK_ERROR, taxonomy.CONNECTION_RESET),
        ),
        (ClientPayloadError(), (taxonomy.NETWORK_ERROR, taxonomy.PAYLOAD_ERROR)),
        (ValueError("boom"), (taxonomy.NETWORK_ERROR, taxonomy.OTHER)),
    ],
)
def test_classify_exception(exc: BaseException, expected: tuple[str, str]) -> None:
    assert classify_exception(exc) == expected


def test_cancelled_is_checked_before_timeout() -> None:
    # regression guard: CancelledError is a BaseException, not Exception
    assert classify_exception(asyncio.CancelledError()) == (
        taxonomy.CANCELLED,
        taxonomy.NONE,
    )


def test_server_timeout_not_misrouted_to_connection_branch() -> None:
    # regression guard on ladder order: ServerTimeoutError is also a
    # ClientConnectionError, so the timeout branch must win.
    assert classify_exception(ServerTimeoutError()) == (
        taxonomy.TIMEOUT,
        taxonomy.READ_TIMEOUT,
    )
