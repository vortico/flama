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

    async def create(self, *data: t.Union[t.Dict[str, t.Any], types.Schema]) -> t.List[t.Tuple[t.Any, ...]]:
        """Creates new elements in the table.

        If the element already exists, it raises an `IntegrityError`. If the element is created, it returns
        the primary key of the element.

        :param data: The data to create the element.
        :return: The primary key of the created element.
        :raises IntegrityError: If the element already exists or cannot be inserted.
        """
        try:
            result = await self._connection.execute(sqlalchemy.insert(self.table), data)
        except sqlalchemy.exc.IntegrityError as e:
            raise exceptions.IntegrityError(str(e))
        return [tuple(x) for x in result.inserted_primary_key_rows]

    async def retrieve(self, *clauses, **filters) -> types.Schema:
        """Retrieves an element from the table.

        If the element does not exist, it raises a `NotFoundError`. If more than one element is found, it raises a
        `MultipleRecordsError`. If the element is found, it returns the element.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements
        using exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param id: The primary key of the element.
        :return: The element.
        :raises NotFoundError: If the element does not exist.
        :raises MultipleRecordsError: If more than one element is found.
        """
        query = self._filter_query(sqlalchemy.select(self.table), *clauses, **filters)

        try:
            element = (await self._connection.execute(query)).one()
        except sqlalchemy.exc.NoResultFound:
            raise exceptions.NotFoundError()
        except sqlalchemy.exc.MultipleResultsFound:
            raise exceptions.MultipleRecordsError()

        return types.Schema(element._asdict())

    async def update(self, data: t.Union[t.Dict[str, t.Any], types.Schema], *clauses, **filters) -> int:
        """Updates elements in the table.

        Using clauses and filters, it filters the elements to update. If no clauses or filters are given, it updates
        all the elements in the table.


        :param id: The primary key of the element.
        :param data: The data to update the element.
        :return: The number of elements updated.
        :raises IntegrityError: If the element cannot be updated.
        """
        query = self._filter_query(sqlalchemy.update(self.table), *clauses, **filters).values(**data)

        try:
            result = await self._connection.execute(query)
        except sqlalchemy.exc.IntegrityError:
            raise exceptions.IntegrityError

        return result.rowcount

    async def delete(self, *clauses, **filters) -> None:
        """Delete elements from the table.

        If no clauses or filters are given, it deletes all the elements in the repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :raises NotFoundError: If the element does not exist.
        :raises MultipleRecordsError: If more than one element is found.
        """
        await self.retrieve(*clauses, **filters)

        query = self._filter_query(sqlalchemy.delete(self.table), *clauses, **filters)

        await self._connection.execute(query)

    async def list(self, *clauses, **filters) -> t.AsyncIterable[types.Schema]:
        """Lists all the elements in the table.

        If no elements are found, it returns an empty list. If no clauses or filters are given, it returns all the
        elements in the repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: Async iterable of the elements.
        """
        query = self._filter_query(sqlalchemy.select(self.table), *clauses, **filters)

        result = await self._connection.stream(query)

        async for row in result:
            yield types.Schema(row._asdict())

    async def drop(self, *clauses, **filters) -> int:
        """Drops elements in the table.

        Returns the number of elements dropped. If no clauses or filters are given, it deletes all the elements in the
        table.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The number of elements dropped.
        """
        query = self._filter_query(sqlalchemy.delete(self.table), *clauses, **filters)

        result = await self._connection.execute(query)

        return result.rowcount

    def _filter_query(self, query, *clauses, **filters):
        """Filters a query using clauses and filters.

        Returns the filtered query. If no clauses or filters are given, it returns the query without any applying
        filter.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param query: The query to filter.
        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The filtered query.
        """
        where_clauses = tuple(clauses) + tuple(self.table.c[k] == v for k, v in filters.items())

        if where_clauses:
            query = query.where(sqlalchemy.and_(*where_clauses))

        return query


class SQLAlchemyTableRepository(SQLAlchemyRepository):
    _table: t.ClassVar[sqlalchemy.Table]

    def __init__(self, connection: "AsyncConnection"):
        super().__init__(connection)
        self._table_manager = SQLAlchemyTableManager(self._table, connection)

    def __eq__(self, other):
        return isinstance(other, SQLAlchemyTableRepository) and self._table == other._table and super().__eq__(other)

    async def create(self, *data: t.Union[t.Dict[str, t.Any], types.Schema]) -> t.List[t.Tuple[t.Any, ...]]:
        """Creates new elements in the repository.

        If the element already exists, it raises an `exceptions.IntegrityError`. If the element is created, it returns
        the primary key of the element.

        :param data: The data to create the element.
        :return: The primary key of the created element.
        :raises IntegrityError: If the element already exists or cannot be inserted.
        """
        return await self._table_manager.create(*data)

    async def retrieve(self, *clauses, **filters) -> types.Schema:
        """Retrieves an element from the repository.

        If the element does not exist, it raises a `NotFoundError`. If more than one element is found, it raises a
        `MultipleRecordsError`. If the element is found, it returns the element.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements
        using exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The element.
        :raises NotFoundError: If the element does not exist.
        :raises MultipleRecordsError: If more than one element is found.
        """
        return await self._table_manager.retrieve(*clauses, **filters)

    async def update(self, data: t.Union[t.Dict[str, t.Any], types.Schema], *clauses, **filters) -> int:
        """Updates an element in the repository.

        If the element does not exist, it raises a `NotFoundError`. If the element is updated, it returns the updated
        element.

        :param data: The data to update the element.
        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The number of elements updated.
        :raises IntegrityError: If the element cannot be updated.
        """
        return await self._table_manager.update(data, *clauses, **filters)

    async def delete(self, *clauses, **filters) -> None:
        """Deletes an element from the repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements
        using exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param id: The primary key of the element.
        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :raises NotFoundError: If the element does not exist.
        :raises MultipleRecordsError: If more than one element is found.
        """
        return await self._table_manager.delete(*clauses, **filters)

    def list(self, *clauses, **filters) -> t.AsyncIterable[types.Schema]:
        """Lists all the elements in the repository.

        Lists all the elements in the repository that match the clauses and filters. If no clauses or filters are given,
        it returns all the elements in the repository. If no elements are found, it returns an empty list.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"]._in((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: Async iterable of the elements.
        """
        return self._table_manager.list(*clauses, **filters)

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
        return await self._table_manager.drop(*clauses, **filters)
