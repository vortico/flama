import abc
import typing as t

from flama import exceptions
from flama.modules import Module

try:
    import sqlalchemy
    from sqlalchemy import MetaData
    from sqlalchemy.ext.asyncio import create_async_engine

    if t.TYPE_CHECKING:
        from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

    metadata = MetaData()
except Exception:  # pragma: no cover
    sqlalchemy = None  # type: ignore[assignment]
    metadata = None  # type: ignore[assignment]

__all__ = ["metadata", "SQLAlchemyModule"]


class ConnectionManager(abc.ABC):
    def __init__(self, engine: "AsyncEngine") -> None:
        self._engine = engine

    async def open(self) -> "AsyncConnection":
        ...

    async def close(self, connection: "AsyncConnection") -> None:
        ...

    async def begin(self, connection: "AsyncConnection") -> "AsyncTransaction":
        ...

    async def end(self, transaction: "AsyncTransaction", rollback: bool = False) -> None:
        ...

    async def rollback(self, transaction: "AsyncTransaction") -> None:
        ...


class SingleConnectionManager(ConnectionManager):
    def __init__(self, engine: "AsyncEngine") -> None:
        super().__init__(engine)
        self._connection: t.Optional["AsyncConnection"] = None
        self._transaction: t.Optional["AsyncTransaction"] = None
        self._clients = 0

    @property
    def connection(self) -> "AsyncConnection":
        if not self._connection:
            raise exceptions.ApplicationError("Connection not initialised")

        return self._connection

    @property
    def transaction(self) -> "AsyncTransaction":
        if not self._transaction:
            raise exceptions.ApplicationError("Connection not initialised")

        return self._transaction

    async def open(self) -> "AsyncConnection":
        try:
            connection = self.connection
        except exceptions.ApplicationError:
            self._connection = connection = self._engine.connect()
            await self._connection.__aenter__()

        self._clients += 1
        return connection

    async def close(self, connection: "AsyncConnection") -> None:
        self._clients -= 1

        if self._clients == 0:
            await self.connection.__aexit__(None, None, None)

    async def begin(self, connection: "AsyncConnection") -> "AsyncTransaction":
        try:
            transaction = await self.connection.begin_nested()
        except exceptions.ApplicationError:
            self._transaction = transaction = self.connection.begin()

        await transaction
        return transaction

    async def end(self, transaction: "AsyncTransaction", rollback: bool = False) -> None:
        if rollback:
            await self.transaction.rollback()
        else:
            await self.transaction.commit()


class MultipleConnectionManager(ConnectionManager):
    async def open(self) -> "AsyncConnection":
        ...

    async def close(self, connection: "AsyncConnection") -> None:
        ...

    async def begin(self, connection: "AsyncConnection") -> "AsyncTransaction":
        ...

    async def commit(self, transaction: "AsyncTransaction") -> None:
        ...

    async def end(self, transaction: "AsyncTransaction", rollback: bool = False) -> None:
        ...


class SQLAlchemyModule(Module):
    name = "sqlalchemy"

    def __init__(
        self,
        database: t.Optional[str] = None,
        single_connection: bool = False,
        engine_args: t.Optional[t.Dict[str, t.Any]] = None,
    ):
        if sqlalchemy is None:
            raise exceptions.ApplicationError("sqlalchemy[asyncio] must be installed to use SQLAlchemyModule")

        super().__init__()

        self.database = database
        self._metadata: "MetaData" = metadata  # type: ignore[assignment]
        self._engine: t.Optional["AsyncEngine"] = None
        self._engine_args = engine_args or {}
        self._connection_manager: t.Optional["ConnectionManager"] = None
        self._manager_cls: t.Type["ConnectionManager"] = (
            SingleConnectionManager if single_connection else MultipleConnectionManager
        )

    @property
    def engine(self) -> "AsyncEngine":
        if not self._engine:
            raise exceptions.ApplicationError("SQLAlchemyModule not initialised")
        return self._engine

    @property
    def connection_manager(self) -> "ConnectionManager":
        if not self._connection_manager:
            raise exceptions.ApplicationError("SQLAlchemyModule not initialised")
        return self._connection_manager

    @property
    def metadata(self) -> "MetaData":
        return self._metadata

    async def open_connection(self) -> "AsyncConnection":
        return await self.connection_manager.open()

    async def close_connection(self, connection: "AsyncConnection") -> None:
        return await self.connection_manager.close(connection)

    async def begin_transaction(self, connection: "AsyncConnection") -> "AsyncTransaction":
        return await self.connection_manager.begin(connection)

    async def end_transaction(self, transaction: "AsyncTransaction", rollback: bool = False) -> None:
        return await self.connection_manager.end(transaction, rollback)

    async def on_startup(self):
        if self.database:
            self._engine = create_async_engine(self.database, **self._engine_args)
            self._connection_manager = self._manager_cls(self._engine)

    async def on_shutdown(self):
        if self.engine:
            await self.engine.dispose()
