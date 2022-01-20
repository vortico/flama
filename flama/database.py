import typing

from flama.modules import Module

try:
    import sqlalchemy
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
except Exception:  # pragma: no cover
    sqlalchemy = None  # type: ignore

if typing.TYPE_CHECKING:
    from flama import Flama


class DatabaseModule(Module):
    name = "database"

    def __init__(self, app: "Flama", database: str = None, *args, **kwargs):
        super().__init__(app, *args, **kwargs)

        self.engine: typing.Optional[AsyncEngine] = None
        self.metadata: typing.Optional[sqlalchemy.MetaData] = None
        self.connection: typing.Optional[AsyncConnection] = None

        if database:
            assert sqlalchemy is not None, "sqlalchemy[asyncio] must be installed to use DatabaseModule"
            self.engine = create_async_engine(database)
            self.metadata = sqlalchemy.MetaData()

    async def on_startup(self):
        if self.engine:
            self.connection = await self.engine.connect()

    async def on_shutdown(self):
        if self.connection:
            await self.connection.close()
            self.connection = None
