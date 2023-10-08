import abc
import typing as t

from flama import types
from flama.ddd import exceptions

try:
    import sqlalchemy
    import sqlalchemy.exc
except Exception:  # pragma: no cover
    raise AssertionError("`sqlalchemy[asyncio]` must be installed to use crud resources") from None


if t.TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


__all__ = ["AbstractRepository", "SQLAlchemyRepository", "SQLAlchemyTableRepository", "SQLAlchemyTableManager"]


class AbstractRepository(abc.ABC):
    """Base class for repositories."""

    ...


class SQLAlchemyRepository(AbstractRepository):
    """Base class for SQLAlchemy repositories. It provides a connection to the database."""

    def __init__(self, connection: "AsyncConnection"):
        self._connection = connection

    def __eq__(self, other):
        return isinstance(other, SQLAlchemyRepository) and self._connection == other._connection


class SQLAlchemyTableManager:
    def __init__(self, table: sqlalchemy.Table, connection: "AsyncConnection"):
        self._connection = connection
        self.table = table

    def __eq__(self, other):
        return (
            isinstance(other, SQLAlchemyTableManager)
            and self._connection == other._connection
            and self.table == other.table
        )

    @property
    def primary_key(self) -> sqlalchemy.Column:
        """Returns the primary key of the table.

        :return: sqlalchemy.Column: The primary key of the table.
        :raises: exceptions.IntegrityError: If the model has a composed primary key.
        """

        model_pk_columns = list(sqlalchemy.inspect(self.table).primary_key.columns.values())

        if len(model_pk_columns) != 1:
            raise exceptions.IntegrityError("Composed primary keys are not supported")

        return model_pk_columns[0]

    async def create(self, *data: t.Union[t.Dict[str, t.Any], types.Schema]) -> t.Optional[t.List[t.Tuple[t.Any, ...]]]:
        """Creates new elements in the table.

        If the element already exists, it raises an `exceptions.IntegrityError`. If the element is created, it returns
        the primary key of the element.

        :param data: The data to create the element.
        :return: The primary key of the created element.
        :raises: exceptions.IntegrityError: If the element already exists.
        """
        try:
            result = await self._connection.execute(sqlalchemy.insert(self.table), data)
        except sqlalchemy.exc.IntegrityError as e:
            raise exceptions.IntegrityError(str(e))
        return [tuple(x) for x in result.inserted_primary_key_rows] if result.inserted_primary_key_rows else None

    async def retrieve(self, id: t.Any) -> types.Schema:
        """Retrieves an element from the table.

        If the element does not exist, it raises a `NotFoundError`.

        :param id: The primary key of the element.
        :return: The element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        element = (
            await self._connection.execute(
                sqlalchemy.select(self.table).where(self.table.c[self.primary_key.name] == id)
            )
        ).first()

        if element is None:
            raise exceptions.NotFoundError(str(id))

        return types.Schema(element._asdict())

    async def update(self, id: t.Any, data: t.Union[t.Dict[str, t.Any], types.Schema]) -> types.Schema:
        """Updates an element in the table.

        If the element does not exist, it raises a `NotFoundError`. If the element is updated, it returns the updated
        element.

        :param id: The primary key of the element.
        :param data: The data to update the element.
        :return: The updated element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        pk = self.primary_key
        result = await self._connection.execute(
            sqlalchemy.update(self.table).where(self.table.c[pk.name] == id).values(**data)
        )

        if result.rowcount == 0:
            raise exceptions.NotFoundError(id)

        return types.Schema({pk.name: id, **data})

    async def delete(self, id: t.Any) -> None:
        """Deletes an element from the table.

        If the element does not exist, it raises a `NotFoundError`.

        :param id: The primary key of the element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        result = await self._connection.execute(
            sqlalchemy.delete(self.table).where(self.table.c[self.primary_key.name] == id)
        )

        if result.rowcount == 0:
            raise exceptions.NotFoundError(id)

    async def list(self, *clauses, **filters) -> t.List[types.Schema]:
        """Lists all the elements in the table.

        If no elements are found, it returns an empty list. If no clauses or filters are given, it returns all the
        elements in the repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The elements.
        """
        query = sqlalchemy.select(self.table)

        where_clauses = tuple(clauses) + tuple(self.table.c[k] == v for k, v in filters.items())
        if where_clauses:
            query = query.where(sqlalchemy.and_(*where_clauses))

        return [types.Schema(row._asdict()) async for row in await self._connection.stream(query)]

    async def drop(self, *clauses, **filters) -> int:
        """Drops elements in the table.

        Returns the number of elements dropped. If no clauses or filters are given, it deletes all the elements in the
        repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The number of elements dropped.
        """
        query = sqlalchemy.delete(self.table)

        where_clauses = tuple(clauses) + tuple(self.table.c[k] == v for k, v in filters.items())
        if where_clauses:
            query = query.where(sqlalchemy.and_(*where_clauses))

        result = await self._connection.execute(query)
        return result.rowcount


class SQLAlchemyTableRepository(SQLAlchemyRepository):
    _table: t.ClassVar[sqlalchemy.Table]

    def __init__(self, connection: "AsyncConnection"):
        super().__init__(connection)
        self._table_manager = SQLAlchemyTableManager(self._table, connection)

    def __eq__(self, other):
        return isinstance(other, SQLAlchemyTableRepository) and self._table == other._table and super().__eq__(other)

    async def create(self, *data: t.Union[t.Dict[str, t.Any], types.Schema]) -> t.Optional[t.List[t.Tuple[t.Any, ...]]]:
        """Creates new elements in the repository.

        If the element already exists, it raises an `exceptions.IntegrityError`. If the element is created, it returns
        the primary key of the element.

        :param data: The data to create the element.
        :return: The primary key of the created element.
        :raises: exceptions.IntegrityError: If the element already exists.
        """
        return await self._table_manager.create(*data)

    async def retrieve(self, id: t.Any) -> types.Schema:
        """Retrieves an element from the repository.

        If the element does not exist, it raises a `NotFoundError`.

        :param id: The primary key of the element.
        :return: The element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        return await self._table_manager.retrieve(id)

    async def update(self, id: t.Any, data: t.Union[t.Dict[str, t.Any], types.Schema]) -> types.Schema:
        """Updates an element in the repository.

        If the element does not exist, it raises a `NotFoundError`. If the element is updated, it returns the updated
        element.

        :param id: The primary key of the element.
        :param data: The data to update the element.
        :return: The updated element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        return await self._table_manager.update(id, data)

    async def delete(self, id: t.Any) -> None:
        """Deletes an element from the repository.

        If the element does not exist, it raises a `NotFoundError`.

        :param id: The primary key of the element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        return await self._table_manager.delete(id)

    async def list(self, *clauses, **filters) -> t.List[types.Schema]:
        """Lists all the elements in the repository.

        Lists all the elements in the repository that match the clauses and filters. If no clauses or filters are given,
        it returns all the elements in the repository. If no elements are found, it returns an empty list.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The elements.
        """
        return await self._table_manager.list(*clauses, **filters)

    async def drop(self, *clauses, **filters) -> int:
        """Drops elements in the repository.

        Returns the number of elements dropped. If no clauses or filters are given, it deletes all the elements in the
        repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The number of elements dropped.
        """
        return await self._table_manager.drop()
