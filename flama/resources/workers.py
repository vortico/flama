import typing as t

from flama.ddd import SQLAlchemyWorker

if t.TYPE_CHECKING:
    from flama import Flama
    from flama.ddd.repositories import SQLAlchemyTableRepository


class FlamaWorker(SQLAlchemyWorker):
    _repositories: t.ClassVar[t.Dict[str, t.Type["SQLAlchemyTableRepository"]]]

    def __init__(self, app: t.Optional["Flama"] = None):
        super().__init__(app)
        self._init_repositories: t.Optional[t.Dict[str, "SQLAlchemyTableRepository"]] = None

    @property
    def repositories(self) -> t.Dict[str, "SQLAlchemyTableRepository"]:
        assert self._init_repositories, "Repositories not initialized"
        return self._init_repositories

    async def __aenter__(self):
        await self.begin()
        self._init_repositories = {r: cls(self.connection) for r, cls in self._repositories.items()}
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        del self._init_repositories

    def add_repository(self, name: str, cls: t.Type["SQLAlchemyTableRepository"]) -> None:
        self._repositories[name] = cls
