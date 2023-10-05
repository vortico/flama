import uuid
from unittest.mock import Mock, call, patch

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncConnection

from flama import Flama
from flama.ddd import SQLAlchemyRepository, SQLAlchemyTableManager, SQLAlchemyTableRepository, exceptions
from flama.sqlalchemy import SQLAlchemyModule
from tests.utils import SQLAlchemyContext


@pytest.fixture(scope="function")
def app():
    return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})


@pytest.fixture(scope="function")
async def connection(client):
    # Exactly the same behavior than 'async with worker'
    connection_: AsyncConnection = client.app.sqlalchemy.engine.connect()
    await connection_.__aenter__()
    transaction = connection_.begin()
    await transaction.__aenter__()

    yield connection_

    await transaction.__aexit__(None, None, None)
    await connection_.__aexit__(None, None, None)


@pytest.fixture(scope="function")
def tables(app):
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
async def table(client, tables):
    table = tables["single"]

    async with SQLAlchemyContext(client.app, [table]):
        yield table


class TestCaseSQLAlchemyRepository:
    @pytest.fixture(scope="function")
    def connection(self):
        return Mock(spec=AsyncConnection)

    async def test_init(self, connection):
        class Repository(SQLAlchemyRepository):
            ...

        repository = Repository(connection)

        assert repository._connection == connection

    def test_eq(self, connection):
        assert SQLAlchemyRepository(connection) == SQLAlchemyRepository(connection)


class TestCaseSQLAlchemyTableManager:
    @pytest.fixture(scope="function")
    def table_manager(self, table, connection):
        return SQLAlchemyTableManager(table, connection)

    async def test_init(self, table, connection):
        table_manager = SQLAlchemyTableManager(table, connection)

        assert table_manager._connection == connection
        assert table_manager.table == table

    def test_eq(self, table, connection):
        assert SQLAlchemyTableManager(table, connection) == SQLAlchemyTableManager(table, connection)

    @pytest.mark.parametrize(
        ["table", "result", "exception"],
        (
            pytest.param("single", "id", None, id="single_pk"),
            pytest.param(
                "composed", None, exceptions.IntegrityError("Composed primary keys are not supported"), id="composed_pk"
            ),
        ),
        indirect=["exception"],
    )
    async def test_primary_key(self, table, result, exception, tables):
        table_manager = SQLAlchemyTableManager(tables[table], Mock())

        with exception:
            assert table_manager.primary_key.name == result

    @pytest.mark.parametrize(
        ["data", "result", "exception"],
        (
            pytest.param({"name": "foo"}, (1,), None, id="ok"),
            pytest.param({"name": None}, None, exceptions.IntegrityError, id="integrity_error"),
        ),
        indirect=["exception"],
    )
    async def test_create(self, table_manager, data, result, exception):
        with exception:
            assert await table_manager.create(data) == result

    @pytest.mark.parametrize(
        ["data", "result", "exception"],
        (
            pytest.param(1, {"id": 1, "name": "foo"}, None, id="ok"),
            pytest.param(2, None, exceptions.NotFoundError(1), id="not_found"),
        ),
        indirect=["exception"],
    )
    async def test_retrieve(self, data, result, exception, table_manager):
        await table_manager.create({"name": "foo"})

        with exception:
            assert await table_manager.retrieve(data) == result

    @pytest.mark.parametrize(
        ["data", "result", "exception"],
        (
            pytest.param((1, {"name": "bar"}), {"id": 1, "name": "foo"}, None, id="ok"),
            pytest.param((2, {"name": "bar"}), None, exceptions.NotFoundError(1), id="not_found"),
        ),
        indirect=["exception"],
    )
    async def test_update(self, data, result, exception, table_manager):
        id_, data_ = data
        await table_manager.create(data_)

        with exception:
            assert await table_manager.update(id_, {"name": "foo"}) == result

    @pytest.mark.parametrize(
        ["data", "exception"],
        (
            pytest.param(1, None, id="ok"),
            pytest.param(2, exceptions.NotFoundError(1), id="not_found"),
        ),
        indirect=["exception"],
    )
    async def test_delete(self, data, exception, table_manager):
        await table_manager.create({"name": "foo"})

        with exception:
            await table_manager.delete(data)

    @pytest.mark.parametrize(
        ["clauses", "filters", "result"],
        (
            pytest.param([], {}, [{"id": 1, "name": "foo"}, {"id": 2, "name": "bar"}], id="all"),
            pytest.param([lambda x: x.ilike("fo%")], {}, [{"id": 1, "name": "foo"}], id="clauses"),
            pytest.param([], {"name": "foo"}, [{"id": 1, "name": "foo"}], id="filters"),
        ),
    )
    async def test_list(self, clauses, filters, result, table, table_manager):
        await table_manager.create({"name": "foo"})
        await table_manager.create({"name": "bar"})

        r = await table_manager.list(*[c(table.c["name"]) for c in clauses], **filters)

        assert r == result

    async def test_drop(self, table_manager):
        await table_manager.create({"name": "foo"})

        result = await table_manager.drop()

        assert result == 1


class TestCaseSQLAlchemyTableRepository:
    @pytest.fixture(scope="function")
    def table(self):
        return Mock(spec=sqlalchemy.Table)

    @pytest.fixture(scope="function")
    def connection(self):
        return Mock(spec=AsyncConnection)

    @pytest.fixture(scope="function")
    def table_manager(self):
        return Mock(spec=SQLAlchemyTableManager)

    @pytest.fixture(scope="function")
    def repository(self, table, connection, table_manager):
        class Repository(SQLAlchemyTableRepository):
            _table = table

        r = Repository(connection)
        with patch.object(r, "_table_manager", table_manager):
            yield r

    async def test_init(self, table, connection):
        class Repository(SQLAlchemyTableRepository):
            _table = table

        repository = Repository(connection)

        assert repository._connection == connection
        assert repository._table_manager == SQLAlchemyTableManager(table, connection)

    def test_eq(self, table, connection):
        class Repository(SQLAlchemyTableRepository):
            _table = table

        assert Repository(connection) == Repository(connection)

    async def test_create(self, repository, table_manager):
        data = {"foo": "bar"}

        await repository.create(data)

        assert table_manager.create.call_args_list == [call(data)]

    async def test_retrieve(self, repository, table_manager):
        id = uuid.uuid4()

        await repository.retrieve(id)

        assert table_manager.retrieve.call_args_list == [call(id)]

    async def test_update(self, repository, table_manager):
        id = uuid.uuid4()
        data = {"foo": "bar"}

        await repository.update(id, data)

        assert table_manager.update.call_args_list == [call(id, data)]

    async def test_delete(self, repository, table_manager):
        id = uuid.uuid4()

        await repository.delete(id)

        assert table_manager.delete.call_args_list == [call(id)]

    async def test_list(self, repository, table_manager):
        clauses = [Mock(), Mock()]
        filters = {"foo": "bar"}

        await repository.list(*clauses, **filters)

        assert table_manager.list.call_args_list == [call(*clauses, **filters)]

    async def test_drop(self, repository, table_manager):
        await repository.drop()

        assert table_manager.drop.call_args_list == [call()]
