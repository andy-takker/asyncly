class SrvMockerError(Exception):
    """Base exception for srvmocker."""


class SequenceExhausted(SrvMockerError):
    """Raised by SequenceResponse when responses run out and on_exhausted='raise'."""


class UnknownHandlerError(SrvMockerError):
    """Raised when register() is called with a name not declared in any MockRoute."""


class NoMatchError(SrvMockerError):
    """Reserved for internal use; the dispatcher currently raises
    aiohttp.web.HTTPNotFound which clients see as a 404 response."""
