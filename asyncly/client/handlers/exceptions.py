from aiohttp import ClientError
from yarl import URL


class BaseHttpClientException(ClientError):
    pass


class UnhandledStatusException(BaseHttpClientException, KeyError):
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
