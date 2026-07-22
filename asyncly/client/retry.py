import asyncio
import random
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from math import isfinite
from typing import Literal

from aiohttp import ClientConnectionError, ClientPayloadError
from yarl import URL

RetryEventKind = Literal["scheduled", "suppressed", "exhausted"]
RetryReason = Literal[
    "status",
    "exception",
    "method_not_allowed",
    "body_not_replayable",
    "attempts_exhausted",
]

DEFAULT_RETRY_STATUSES = frozenset(
    {
        HTTPStatus.REQUEST_TIMEOUT,
        HTTPStatus.TOO_EARLY,
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    }
)
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE", "PUT", "DELETE"})
DEFAULT_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ClientConnectionError,
    ClientPayloadError,
    asyncio.TimeoutError,
)


@dataclass(frozen=True)
class RetryContext:
    """Immutable description of one physical request attempt.

    ``attempt`` is one-based and describes the attempt that just produced
    ``response_status`` or ``exception``.
    """

    method: str
    url: URL
    attempt: int
    max_attempts: int
    replayable: bool = True
    response_status: int | None = None
    exception: BaseException | None = None

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if not 1 <= self.attempt <= self.max_attempts:
            raise ValueError("attempt must be between 1 and max_attempts")
        if self.response_status is not None and self.exception is not None:
            raise ValueError("response_status and exception are mutually exclusive")
        object.__setattr__(self, "method", self.method.upper())


@dataclass(frozen=True)
class _RetryableResponse:
    context: RetryContext
    retry_after: str | None


BackoffStrategy = Callable[[RetryContext], float]
RetryObserver = Callable[["RetryEvent"], None]


def full_jitter_backoff(context: RetryContext) -> float:
    """Return capped exponential backoff with full jitter.

    The cap starts at 0.5 seconds after the first failed attempt and doubles to
    a maximum of 30 seconds. Pass a deterministic callable to ``RetryPolicy``
    in tests when real jitter is undesirable.
    """

    cap = min(0.5 * (2 ** (context.attempt - 1)), 30.0)
    return random.uniform(0.0, cap)


@dataclass(frozen=True)
class RetryPolicy:
    """Policy controlling whether and when an HTTP request is retried."""

    max_attempts: int = 3
    statuses: Collection[int] = field(default_factory=lambda: DEFAULT_RETRY_STATUSES)
    exceptions: tuple[type[BaseException], ...] = DEFAULT_RETRY_EXCEPTIONS
    methods: Collection[str] = field(default_factory=lambda: IDEMPOTENT_METHODS)
    backoff: BackoffStrategy = full_jitter_backoff
    respect_retry_after: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        statuses = frozenset(self.statuses)
        invalid_statuses = sorted(
            status for status in statuses if not 100 <= status <= 599
        )
        if invalid_statuses:
            raise ValueError(
                f"statuses must contain valid HTTP status codes: {invalid_statuses}"
            )
        methods = frozenset(method.upper() for method in self.methods)
        if any(not method for method in methods):
            raise ValueError("methods must not contain empty values")
        if not all(
            isinstance(exc_type, type) and issubclass(exc_type, BaseException)
            for exc_type in self.exceptions
        ):
            raise TypeError("exceptions must contain exception classes")

        object.__setattr__(self, "statuses", statuses)
        object.__setattr__(self, "methods", methods)
        object.__setattr__(self, "exceptions", tuple(self.exceptions))

    def should_retry(self, context: RetryContext) -> bool:
        """Return whether ``context`` is eligible for another attempt."""

        return (
            self._matches_outcome(context)
            and context.method in self.methods
            and context.replayable
            and context.attempt < self.max_attempts
        )

    def get_delay(
        self,
        context: RetryContext,
        *,
        retry_after: str | None = None,
        now: datetime | None = None,
    ) -> float:
        """Return the delay before the next attempt.

        A valid HTTP ``Retry-After`` value takes precedence when enabled;
        otherwise the configured backoff strategy is used.
        """

        delay = None
        if self.respect_retry_after and retry_after is not None:
            delay = _parse_retry_after(retry_after, now=now)
        if delay is None:
            delay = float(self.backoff(context))
        if not isfinite(delay) or delay < 0:
            raise ValueError("retry delay must be a finite non-negative number")
        return delay

    def _matches_outcome(self, context: RetryContext) -> bool:
        if isinstance(context.exception, asyncio.CancelledError):
            return False
        if context.response_status is not None:
            return context.response_status in self.statuses
        if context.exception is not None:
            return isinstance(context.exception, self.exceptions)
        return False

    def _suppression_reason(self, context: RetryContext) -> RetryReason | None:
        if not self._matches_outcome(context):
            return None
        if context.method not in self.methods:
            return "method_not_allowed"
        if not context.replayable:
            return "body_not_replayable"
        if context.attempt >= self.max_attempts:
            return "attempts_exhausted"
        return None


@dataclass(frozen=True)
class RetryEvent:
    """Notification emitted for a retry decision."""

    kind: RetryEventKind
    context: RetryContext
    delay: float = 0.0
    reason: RetryReason = "status"

    def __post_init__(self) -> None:
        if not isfinite(self.delay) or self.delay < 0:
            raise ValueError("delay must be a finite non-negative number")


def _parse_retry_after(value: str, *, now: datetime | None = None) -> float | None:
    stripped = value.strip()
    if stripped.isdigit():
        return float(stripped)

    try:
        retry_at = parsedate_to_datetime(stripped)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at is None:
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - current).total_seconds())
