import subprocess
import sys

import pytest

from flama import Flama
from flama.client import Client
from flama.ddd.repositories.http import HTTPRepository
from flama.ddd.repositories.sqlalchemy import SQLAlchemyRepository
from flama.exceptions import ApplicationError
from flama.resources.workers import ResourcesWorker
from flama.sqlalchemy import SQLAlchemyModule


class TestCaseResourcesWorker:
    @pytest.fixture(scope="function")
    async def app(self):
        app_ = Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})
        async with Client(app=app_):
            yield app_

    @pytest.fixture(scope="function")
    def worker(self):
        class FooWorker(ResourcesWorker): ...

        return FooWorker()

    @pytest.fixture(scope="function")
    def sqlalchemy_repository(self):
        class FooRepository(SQLAlchemyRepository): ...

        return FooRepository

    @pytest.fixture(scope="function")
    def http_repository(self):
        class BarRepository(HTTPRepository): ...

        return BarRepository

    def test_init(self) -> None:
        worker = ResourcesWorker()

        assert not worker._resources_repositories.registered

    def test_import_without_sqlalchemy(self) -> None:
        code = (
            "import sys; sys.modules['sqlalchemy'] = None\n"
            "from flama import Flama\n"
            "from flama.resources.workers import ResourcesWorker\n"
            "app = Flama(schema=None, docs=None)\n"
            "assert isinstance(app.resources.worker, ResourcesWorker)\n"
            "print(','.join(m for m in sys.modules if m.startswith('sqlalchemy') and sys.modules[m] is not None))"
        )

        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

        assert result.stdout.strip() == ""

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(ApplicationError("Repositories not initialized"), id="not_initialised")],
        indirect=["exception"],
    )
    def test_repositories_property_raises_when_uninitialised(self, worker, exception) -> None:
        with exception:
            worker.repositories

    async def test_async_context(self, app, worker, http_repository, sqlalchemy_repository) -> None:
        worker.app = app
        worker.add_repository("foo", sqlalchemy_repository)
        worker.add_repository("bar", http_repository)

        async with worker:
            assert worker.repositories == {
                "foo": sqlalchemy_repository(worker.connection),
                "bar": http_repository(worker.connection),
            }

        worker.remove_repository("bar")

        async with worker:
            assert worker.repositories == {"foo": sqlalchemy_repository(worker.connection)}
