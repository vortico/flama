import typing as t

from flama.ddd.workers.base import BaseWorker

if t.TYPE_CHECKING:
    from flama import Flama
    from flama.client import Client

__all__ = ["HTTPWorker"]


class HTTPWorker(BaseWorker):
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

    @client.setter
    def client(self, client: "Client") -> None:
        """Set the client to interact with an HTTP resource.

        :param client: Flama client.
        """
        self._client = client

    @client.deleter
    def client(self) -> None:
        """Delete the client."""
        del self._client

    async def set_up(self) -> None:
        """Initialize the client with the URL."""
        from flama.client import Client

        self.client = Client(base_url=self.url, **self._client_kwargs)

        await self.client.__aenter__()

    async def tear_down(self, *, rollback: bool = False) -> None:
        """Close and delete the client.

        :param rollback: If the unit of work should be rolled back.
        """
        await self.client.__aexit__()
        del self.client

    async def repository_params(self) -> tuple[list[t.Any], dict[str, t.Any]]:
        """Get the parameters for initialising the repositories.

        :return: Parameters for initialising the repositories.
        """
        return [self.client], {}

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
