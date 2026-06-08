import inspect
import uuid
from unittest.mock import Mock, call, patch

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncConnection

from flama.ddd import exceptions
from flama.ddd.repositories.sqlalchemy import SQLAlchemyRepository, SQLAlchemyTableManager, SQLAlchemyTableRepository
from tests._utils import SQLAlchemyContext


@pytest.fixture(scope="function")
async def connection(client):
    # Exactly the same behavior as 'async with worker'
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
        class Repository(SQLAlchemyRepository): ...

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
        ["data", "result", "exception"],
        (
            pytest.param(
                [{"name": "foo"}],
                [{"id": 1, "name": "foo"}],
                None,
                id="single",
            ),
            pytest.param(
                [{"name": "foo"}, {"name": "bar"}],
                [{"id": 1, "name": "foo"}, {"id": 2, "name": "bar"}],
                None,
                id="multiple",
            ),
            pytest.param(
                [{"name": None}],
                None,
                exceptions.IntegrityError,
                id="integrity_error",
            ),
        ),
        indirect=["exception"],
    )
    async def test_create(self, table_manager, data, result, exception):
        with exception:
            assert await table_manager.create(*data) == result

    @pytest.mark.parametrize(
        ["clauses", "filters", "result", "exception"],
        (
            pytest.param(
                [],
                {"id": 1},
                {"id": 1, "name": "foo"},
                None,
                id="ok",
            ),
            pytest.param(
                [],
                {"id": 0},
                None,
                exceptions.NotFoundError(resource="repository_table_single_pk"),
                id="not_found",
            ),
            pytest.param(
                [lambda x: x.ilike("fo%")],
                {},
                None,
                exceptions.MultipleRecordsError(resource="repository_table_single_pk"),
                id="multiple_results",
            ),
        ),
        indirect=["exception"],
    )
    async def test_retrieve(self, clauses, filters, result, exception, table, table_manager):
        await table_manager.create({"name": "foo"}, {"name": "foo"})

        with exception:
            assert await table_manager.retrieve(*[c(table.c["name"]) for c in clauses], **filters) == result

    @pytest.mark.parametrize(
        ["clauses", "filters", "data", "result", "exception"],
        (
            pytest.param(
                [],
                {"id": 1},
                {"name": "bar"},
                [{"id": 1, "name": "bar"}],
                None,
                id="ok",
            ),
            pytest.param(
                [],
                {"id": 0},
                {"name": "bar"},
                [],
                None,
                id="not_found",
            ),
            pytest.param(
                [],
                {"id": 1},
                {"name": None},
                [{"id": 1, "name": None}],
                exceptions.IntegrityError,
                id="integrity_error",
            ),
            pytest.param(
                [lambda x: x.ilike("fo%")],
                {},
                {"name": "bar"},
                [{"id": 1, "name": "bar"}, {"id": 2, "name": "bar"}],
                None,
                id="multiple_results",
            ),
        ),
        indirect=["exception"],
    )
    async def test_update(self, clauses, filters, data, result, exception, table, table_manager):
        await table_manager.create({"name": "foo"}, {"name": "foo"})

        with exception:
            assert await table_manager.update(data, *[c(table.c["name"]) for c in clauses], **filters) == result

    @pytest.mark.parametrize(
        ["clauses", "filters", "exception"],
        (
            pytest.param(
                [],
                {"id": 1},
                None,
                id="ok",
            ),
            pytest.param(
                [],
                {"id": 0},
                exceptions.NotFoundError(resource="repository_table_single_pk"),
                id="not_found",
            ),
            pytest.param(
                [lambda x: x.ilike("fo%")],
                {},
                exceptions.MultipleRecordsError,
                id="multiple_results",
            ),
        ),
        indirect=["exception"],
    )
    async def test_delete(self, clauses, filters, exception, table, table_manager):
        await table_manager.create({"name": "foo"}, {"name": "foo"})

        with exception:
            await table_manager.delete(*[c(table.c["name"]) for c in clauses], **filters)

    @pytest.mark.parametrize(
        ["clauses", "order_by", "order_direction", "filters", "result"],
        (
            pytest.param([], None, None, {}, [{"id": 1, "name": "foo"}, {"id": 2, "name": "bar"}], id="all"),
            pytest.param([lambda x: x.ilike("fo%")], None, None, {}, [{"id": 1, "name": "foo"}], id="clauses"),
            pytest.param([], "name", "asc", {}, [{"id": 2, "name": "bar"}, {"id": 1, "name": "foo"}], id="order"),
            pytest.param([], None, None, {"name": "foo"}, [{"id": 1, "name": "foo"}], id="filters"),
        ),
    )
    async def test_list(self, clauses, order_by, order_direction, filters, result, table, table_manager):
        await table_manager.create({"name": "foo"}, {"name": "bar"})

        r = [
            x
            async for x in table_manager.list(
                *[c(table.c["name"]) for c in clauses], order_by=order_by, order_direction=order_direction, **filters
            )
        ]

        assert r == result

    @pytest.mark.parametrize(
        ["clauses", "filters", "result"],
        (
            pytest.param([], {}, 2, id="all"),
            pytest.param([lambda x: x.ilike("fo%")], {}, 1, id="clauses"),
            pytest.param([], {"name": "foo"}, 1, id="filters"),
        ),
    )
    async def test_drop(self, clauses, filters, result, table, table_manager):
        await table_manager.create({"name": "foo"}, {"name": "bar"})

        r = await table_manager.drop(*[c(table.c["name"]) for c in clauses], **filters)

        assert r == result


class TestCaseSQLAlchemyTableRepository:
    @pytest.fixture(scope="function")
    def table(self):
        mock = Mock(spec=sqlalchemy.Table)
        mock.name = "foo"
        return mock

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

        repository = Repository(connection)
        assert repository == Repository(connection)
        assert repository != Repository(Mock(spec=AsyncConnection))

    @pytest.mark.parametrize(
        ["method", "args", "kwargs"],
        [
            pytest.param("create", ({"foo": "bar"},), {}, id="create"),
            pytest.param("retrieve", (uuid.uuid4(),), {}, id="retrieve"),
            pytest.param("update", (uuid.uuid4(), {"foo": "bar"}), {}, id="update"),
            pytest.param("delete", (uuid.uuid4(),), {}, id="delete"),
            pytest.param(
                "list",
                (Mock(), Mock()),
                {"order_by": "foo", "order_direction": "desc", "foo": "bar"},
                id="list",
            ),
            pytest.param("drop", (), {}, id="drop"),
        ],
    )
    async def test_delegation(self, repository, table_manager, method, args, kwargs):
        result = getattr(repository, method)(*args, **kwargs)
        if inspect.iscoroutine(result):
            await result

        assert getattr(table_manager, method).call_args_list == [call(*args, **kwargs)]
