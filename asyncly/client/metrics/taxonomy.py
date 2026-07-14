"""Normalize client exceptions into low-cardinality metric labels.

The best-practice guidance for HTTP-client instrumentation splits failures into a
small, fixed ``outcome`` set (for logical/operation success rate) and a slightly
richer ``error_type`` set (for diagnosing *where* a failure happened). Putting the
raw exception class name into a label is discouraged: it is unbounded and leaks
implementation detail. :func:`classify_exception` maps aiohttp/asyncio exceptions
onto those fixed vocabularies.
"""

import asyncio
import errno
import socket

from aiohttp import (
    ClientConnectorCertificateError,
    ClientConnectorDNSError,
    ClientConnectorError,
    ClientConnectorSSLError,
    ClientOSError,
    ClientPayloadError,
    ClientSSLError,
    ConnectionTimeoutError,
    ServerDisconnectedError,
    ServerTimeoutError,
)

# ``outcome`` values — the compact set used for success-rate math.
RESPONSE = "response"
TIMEOUT = "timeout"
NETWORK_ERROR = "network_error"
CANCELLED = "cancelled"

# ``outcome`` collapsed to two values for the duration histogram, where every
# extra label multiplies the number of buckets.
RESPONSE_OUTCOME = "response"
ERROR_OUTCOME = "error"

# ``error_type`` values — the richer diagnostic set. ``none`` marks success.
NONE = "none"
DNS_ERROR = "dns_error"
CONNECT_ERROR = "connect_error"
TLS_ERROR = "tls_error"
CONNECTION_RESET = "connection_reset"
READ_TIMEOUT = "read_timeout"
SERVER_DISCONNECTED = "server_disconnected"
PAYLOAD_ERROR = "payload_error"
# A response arrived but handling it failed (deserialization, validation, or no
# matching status handler). Not a transport failure.
INVALID_RESPONSE = "invalid_response"
OTHER = "other"


def _is_dns_error(exc: BaseException) -> bool:
    # aiohttp wraps the underlying resolver failure in ``os_error``.
    return isinstance(getattr(exc, "os_error", None), socket.gaierror)


def classify_exception(exc: BaseException) -> tuple[str, str]:
    """Return ``(outcome, error_type)`` for a failed request.

    A successful request never reaches this function; the caller reports
    ``("response", "none")`` directly.

    The isinstance ladder is ordered most-specific first because the aiohttp
    hierarchy overlaps: ``ServerTimeoutError`` is both a ``ClientConnectionError``
    and a ``TimeoutError``, and ``ClientConnectorSSLError`` is a subclass of
    ``ClientConnectorError`` which is a subclass of ``ClientOSError``. Reordering
    these branches silently changes the emitted labels.
    """
    # CancelledError is a BaseException, not an Exception — check it first and
    # separately so a caller's broad ``except Exception`` can never swallow it.
    if isinstance(exc, asyncio.CancelledError):
        return CANCELLED, NONE

    # Timeouts. ConnectionTimeoutError (a ServerTimeoutError subclass) is a
    # timeout while establishing the connection, so tag it as a connect problem.
    if isinstance(exc, ConnectionTimeoutError):
        return TIMEOUT, CONNECT_ERROR
    if isinstance(exc, ServerTimeoutError | TimeoutError):
        return TIMEOUT, READ_TIMEOUT

    # TLS problems sit above the generic connector branch.
    if isinstance(
        exc,
        ClientConnectorSSLError | ClientConnectorCertificateError | ClientSSLError,
    ):
        return NETWORK_ERROR, TLS_ERROR

    # DNS resolution failures (also a ClientConnectorError subclass).
    if isinstance(exc, ClientConnectorDNSError) or _is_dns_error(exc):
        return NETWORK_ERROR, DNS_ERROR

    if isinstance(exc, ClientConnectorError):
        return NETWORK_ERROR, CONNECT_ERROR

    if isinstance(exc, ServerDisconnectedError):
        return NETWORK_ERROR, SERVER_DISCONNECTED

    # Connection reset — either the builtin OSError or an aiohttp ClientOSError
    # carrying ECONNRESET.
    is_reset = getattr(exc, "errno", None) == errno.ECONNRESET
    if isinstance(exc, ConnectionResetError) or (
        isinstance(exc, ClientOSError) and is_reset
    ):
        return NETWORK_ERROR, CONNECTION_RESET

    if isinstance(exc, ClientPayloadError):
        return NETWORK_ERROR, PAYLOAD_ERROR

    return NETWORK_ERROR, OTHER
