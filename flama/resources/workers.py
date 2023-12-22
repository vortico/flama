import typing as t

from flama.ddd import SQLAlchemyWorker
from flama.exceptions import ApplicationError

if t.TYPE_CHECKING:
    from flama import Flama
    from flama.ddd.repositories import SQLAlchemyTableRepository


class FlamaWorker(SQLAlchemyWorker):
    """The worker used by Flama Resources."""

    def __init__(self, app: t.Optional["Flama"] = None):
        """Initialize the worker.

        This special worker is used to handle the repositories created by Flama Resources.

        :param app: The application instance.
        """

        super().__init__(app)
        self._repositories: t.Dict[str, t.Type["SQLAlchemyTableRepository"]] = {}  # type: ignore
        self._init_repositories: t.Optional[t.Dict[str, "SQLAlchemyTableRepository"]] = None

    @property
    def repositories(self) -> t.Dict[str, "SQLAlchemyTableRepository"]:
        """Get the initialized repositories.

        :retirns: The initialized repositories.
        :raises ApplicationError: If the repositories are not initialized.
        """
        if not self._init_repositories:
            raise ApplicationError("Repositories not initialized")

        return self._init_repositories

    async def begin(self) -> None:
        """Start a unit of work.

        Initialize the connection, begin a transaction, and create the repositories.
        """
        await self.begin_transaction()
        self._init_repositories = {r: cls(self.connection) for r, cls in self._repositories.items()}

    async def end(self, *, rollback: bool = False) -> None:
        """End a unit of work.

        Close the connection, commit or rollback the transaction, and delete the repositories.

        :param rollback: If the unit of work should be rolled back.
        """
        await self.end_transaction(rollback=rollback)
        del self._init_repositories
