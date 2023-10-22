import pytest

from flama import Flama
from flama.ddd.repositories import AbstractRepository
from flama.ddd.workers import AbstractWorker
from flama.sqlalchemy import SQLAlchemyModule


@pytest.fixture(scope="function")
def app():
    return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})


@pytest.fixture(scope="function")
def repository():
    class FooRepository(AbstractRepository):
        ...

    return FooRepository


@pytest.fixture(scope="function")
def worker(repository):
    class FooWorker(AbstractWorker):
        bar: repository

        async def begin(self):
            ...

        async def end(self, *, rollback: bool = False):
            ...

        async def commit(self):
            ...

        async def rollback(self):
            ...

    return FooWorker()
