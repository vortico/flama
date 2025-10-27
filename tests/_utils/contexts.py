import sqlalchemy

from flama import Flama

__all__ = ["ExceptionContext", "SQLAlchemyContext"]


class ExceptionContext:
    def __init__(self, context, exception: Exception | None = None):
        self.context = context
        self.exception = exception

    def __enter__(self):
        return self.context.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.context.__exit__(exc_type, exc_val, exc_tb)

    def __bool__(self) -> bool:
        return self.exception is not None


class SQLAlchemyContext:
    def __init__(self, app: Flama, tables: list[sqlalchemy.Table]):
        self.app = app
        self.tables = tables

    async def __aenter__(self):
        async with self.app.sqlalchemy.engine.begin() as connection:
            await connection.run_sync(self.app.sqlalchemy.metadata.create_all, tables=self.tables)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self.app.sqlalchemy.engine.begin() as connection:
            await connection.run_sync(self.app.sqlalchemy.metadata.drop_all, tables=self.tables)
