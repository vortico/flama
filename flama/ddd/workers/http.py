import typing as t

from flama.ddd.workers.base import AbstractWorker

if t.TYPE_CHECKING:
    from flama import Flama
    from flama.client import Client

__all__ = ["HTTPWorker"]


class HTTPWorker(AbstractWorker):
    """Worker for HTTP client.

    It will provide a flama Client and create the repositories for the corresponding resources.
    """

    _client: "Client"

    def __init__(self, url: t.Union[str, t.Callable[[], str]], app: t.Optional["Flama"] = None, **client_kwargs: t.Any):
        super().__init__(app=app)
        self._url = url
        self._client_kwargs = client_kwargs

    @property
    def url(self) -> str:
        return self._url() if callable(self._url) else self._url

    @property
    def client(self) -> "Client":
        """Client to interact with an HTTP resource

        :return: Flama client.
        :raises AttributeError: If the client is not initialized.
        """
        try:
            return self._client
        except AttributeError:
            raise AttributeError("Client not initialized")

    async def begin_transaction(self) -> None:
        """Initialize the client with the URL."""
        await self._client.__aenter__()

    async def end_transaction(self) -> None:
        """Close and delete the client."""
        await self.client.__aexit__()

    async def begin(self) -> None:
        """Start a unit of work.

        Initialize the client, and create the repositories.
        """
        from flama.client import Client

        self._client = Client(base_url=self.url, **self._client_kwargs)

        await self.begin_transaction()

        for repository, repository_class in self._repositories.items():
            setattr(self, repository, repository_class(self._client))

    async def end(self, *, rollback: bool = False) -> None:
        """End a unit of work.

        Close the client, and delete the repositories.
        """
        await self.end_transaction()

        for repository in self._repositories.keys():
            delattr(self, repository)

        del self._client

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
