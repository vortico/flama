import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncConnection

from flama import Flama
from flama.ddd import SQLAlchemyRepository, exceptions
from flama.sqlalchemy import SQLAlchemyModule
from tests.utils import SQLAlchemyContext


class TestCaseSQLAlchemyRepository:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})

    @pytest.fixture(scope="function")
    async def connection(self, client):
        # Exactly the same behavior than 'async with worker'
        connection_: AsyncConnection = client.app.sqlalchemy.engine.connect()
        await connection_.__aenter__()
        transaction = connection_.begin()
        await transaction.__aenter__()

        yield connection_

        await transaction.__aexit__(None, None, None)
        await connection_.__aexit__(None, None, None)

    @pytest.fixture(scope="function")
    def tables(self, app):
        return {
            "single": sqlalchemy.Table(
                "repository_table_single_pk",
                app.sqlalchemy.metadata,
                sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
                sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
            ),
            "composed": sqlalchemy.Table(
                "repository_table_composed_pk",
                app.sqlalchemy.metadata,
                sqlalchemy.Column("id_first", sqlalchemy.Integer, primary_key=True),
                sqlalchemy.Column("id_second", sqlalchemy.Integer, primary_key=True),
                sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
            ),
        }

    @pytest.fixture(scope="function")
    async def table(self, client, tables):
        table = tables["single"]

        async with SQLAlchemyContext(client.app, [table]):
            yield table

    @pytest.fixture(scope="function")
    def repository(self, table, connection):
        class Repository(SQLAlchemyRepository):
            _table = table

        return Repository(connection)

    @pytest.fixture(scope="function")
    async def repository_select(self, request, client, tables, connection):
        table = tables[request.param]

        async with SQLAlchemyContext(client.app, [table]):

            class Repository(SQLAlchemyRepository):
                _table = tables[request.param]

            yield Repository(connection)

    @pytest.mark.parametrize(
        ["repository_select", "result", "exception"],
        (
            pytest.param("single", "id", None, id="single_pk"),
            pytest.param(
                "composed", None, exceptions.IntegrityError("Composed primary keys are not supported"), id="composed_pk"
            ),
        ),
        indirect=["repository_select", "exception"],
    )
    async def test_primary_key(self, repository_select, result, exception):
        with exception:
            assert repository_select.primary_key.name == result

    @pytest.mark.parametrize(
        ["data", "result", "exception"],
        (
            pytest.param({"name": "foo"}, (1,), None, id="ok"),
            pytest.param({"name": None}, None, exceptions.IntegrityError, id="integrity_error"),
        ),
        indirect=["exception"],
    )
    async def test_create(self, repository, data, result, exception):
        with exception:
            assert await repository.create(data) == result

    @pytest.mark.parametrize(
        ["data", "result", "exception"],
        (
            pytest.param(1, {"id": 1, "name": "foo"}, None, id="ok"),
            pytest.param(2, None, exceptions.NotFoundError(1), id="not_found"),
        ),
        indirect=["exception"],
    )
    async def test_retrieve(self, data, result, exception, repository):
        await repository.create({"name": "foo"})

        with exception:
            assert await repository.retrieve(data) == result

    @pytest.mark.parametrize(
        ["data", "result", "exception"],
        (
            pytest.param((1, {"name": "bar"}), {"id": 1, "name": "foo"}, None, id="ok"),
            pytest.param((2, {"name": "bar"}), None, exceptions.NotFoundError(1), id="not_found"),
        ),
        indirect=["exception"],
    )
    async def test_update(self, data, result, exception, repository):
        id_, data_ = data
        await repository.create(data_)

        with exception:
            assert await repository.update(id_, {"name": "foo"}) == result

    @pytest.mark.parametrize(
        ["data", "result", "exception"],
        (
            pytest.param(1, {"id": 1, "name": "foo"}, None, id="ok"),
            pytest.param(2, None, exceptions.NotFoundError(1), id="not_found"),
        ),
        indirect=["exception"],
    )
    async def test_delete(self, data, result, exception, repository):
        await repository.create({"name": "foo"})

        with exception:
            await repository.delete(data)

    @pytest.mark.parametrize(
        ["clauses", "filters", "result"],
        (
            pytest.param([], {}, [{"id": 1, "name": "foo"}, {"id": 2, "name": "bar"}], id="all"),
            pytest.param([lambda x: x.ilike("fo%")], {}, [{"id": 1, "name": "foo"}], id="clauses"),
            pytest.param([], {"name": "foo"}, [{"id": 1, "name": "foo"}], id="filters"),
        ),
    )
    async def test_list(self, clauses, filters, result, repository):
        await repository.create({"name": "foo"})
        await repository.create({"name": "bar"})

        r = await repository.list(*[c(repository._table.c["name"]) for c in clauses], **filters)

        assert r == result

    async def test_drop(self, repository):
        await repository.create({"name": "foo"})

        result = await repository.drop()

        assert result == 1
