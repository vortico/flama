import typing as t

from flama.modules import Module

try:
    import sqlalchemy
    from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

    metadata = sqlalchemy.MetaData()
except Exception:  # pragma: no cover
    sqlalchemy = None  # type: ignore[assignment]
    metadata = None  # type: ignore[assignment]

__all__ = ["metadata", "SQLAlchemyModule"]


class SQLAlchemyModule(Module):
    name = "sqlalchemy"

    def __init__(self, database: t.Optional[str] = None):
        super().__init__()

        self.database = database
        self._engine: t.Optional["AsyncEngine"] = None
        self._metadata: t.Optional["sqlalchemy.MetaData"] = metadata

    @property
    def engine(self) -> t.Optional["AsyncEngine"]:
        assert sqlalchemy is not None, "sqlalchemy[asyncio] must be installed to use SQLAlchemyModule."
        return self._engine

    @engine.setter
    def engine(self, value: "AsyncEngine"):
        self._engine = value

    @engine.deleter
    def engine(self):
        self._engine = None

    @property
    def metadata(self) -> t.Optional["sqlalchemy.MetaData"]:
        assert sqlalchemy is not None, "sqlalchemy[asyncio] must be installed to use SQLAlchemyModule."
        return self._metadata

    async def on_startup(self):
        if self.database:
            self.engine = create_async_engine(self.database)

    async def on_shutdown(self):
        if self.engine:
            await self.engine.dispose()
