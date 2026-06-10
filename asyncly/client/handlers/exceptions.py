from aiohttp import ClientError
from yarl import URL


class BaseHttpClientException(ClientError):
    """Base class for exceptions raised by `BaseHttpClient`."""


class UnhandledStatusException(BaseHttpClientException, KeyError):
    """Raised when a response status has no matching handler.

    Attributes:
        status: The unmatched response status code.
        url: The request URL.
        client_name: The originating client's name, if known.
    """

    status: int
    url: URL
    client_name: str | None

    def __init__(
        self,
        message: str,
        status: int,
        url: URL,
        client_name: str | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.url = url
        self.client_name = client_name
