import typing as t

from flama import exceptions
from flama.ddd import exceptions as ddd_exceptions
from flama.ddd.repositories import BaseRepository

try:
    import sqlalchemy
    import sqlalchemy.exc as sqlalchemy_exceptions
    from sqlalchemy.ext.asyncio import AsyncConnection
except Exception:  # pragma: no cover
    raise exceptions.DependencyNotInstalled(
        dependency=exceptions.DependencyNotInstalled.Dependency.sqlalchemy, dependant=__name__
    )


__all__ = ["SQLAlchemyRepository", "SQLAlchemyTableManager", "SQLAlchemyTableRepository"]


class SQLAlchemyRepository(BaseRepository):
    """Base class for SQLAlchemy repositories. It provides a connection to the database."""

    def __init__(self, connection: AsyncConnection, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._connection = connection

    def __eq__(self, other):
        return isinstance(other, SQLAlchemyRepository) and self._connection == other._connection


class SQLAlchemyTableManager:
    def __init__(self, table: sqlalchemy.Table, connection: AsyncConnection):  # type: ignore
        self._connection = connection
        self.table = table
        self.resource = table.name

    def __eq__(self, other):
        return (
            isinstance(other, SQLAlchemyTableManager)
            and self._connection == other._connection
            and self.table == other.table
        )

    async def create(self, *data: dict[str, t.Any]) -> list[dict[str, t.Any]]:
        """Creates new elements in the table.

        If the element already exists, it raises an `IntegrityError`. If the element is created, it returns
        the primary key of the element.

        :param data: The data to create the elements.
        :return: The created elements.
        :raises IntegrityError: If the element already exists or cannot be inserted.
        """
        try:
            result = await self._connection.execute(sqlalchemy.insert(self.table).values(data).returning(self.table))
        except sqlalchemy_exceptions.IntegrityError:
            raise ddd_exceptions.IntegrityError(resource=self.resource)
        return [dict[str, t.Any](element._asdict()) for element in result]

    async def retrieve(self, *clauses, **filters) -> dict[str, t.Any]:
        """Retrieves an element from the table.

        If the element does not exist, it raises a `NotFoundError`. If more than one element is found, it raises a
        `MultipleRecordsError`. If the element is found, it returns the element.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements
        using exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"].in_((1, 2, 3))`
        Filter example: `id=1`

        :return: The element.
        :raises NotFoundError: If the element does not exist.
        :raises MultipleRecordsError: If more than one element is found.
        """
        query = self._filter_query(sqlalchemy.select(self.table), *clauses, **filters)

        try:
            element = (await self._connection.execute(query)).one()
        except sqlalchemy_exceptions.NoResultFound:
            raise ddd_exceptions.NotFoundError(resource=self.resource)
        except sqlalchemy_exceptions.MultipleResultsFound:
            raise ddd_exceptions.MultipleRecordsError(resource=self.resource)

        return dict[str, t.Any](element._asdict())

    async def update(self, data: dict[str, t.Any], *clauses, **filters) -> list[dict[str, t.Any]]:
        """Updates elements in the table.

        Using clauses and filters, it filters the elements to update. If no clauses or filters are given, it updates
        all the elements in the table.

        :param data: The data to update the elements.
        :return: The updated elements.
        :raises IntegrityError: If the elements cannot be updated.
        """
        query = (
            self._filter_query(sqlalchemy.update(self.table), *clauses, **filters).values(**data).returning(self.table)
        )

        try:
            result = await self._connection.execute(query)
        except sqlalchemy_exceptions.IntegrityError:
            raise ddd_exceptions.IntegrityError(resource=self.resource)

        return [dict[str, t.Any](element._asdict()) for element in result]

    async def delete(self, *clauses, **filters) -> None:
        """Delete an element from the table.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"].in_((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :raises NotFoundError: If the element does not exist.
        :raises MultipleRecordsError: If more than one element is found.
        """
        await self.retrieve(*clauses, **filters)

        query = self._filter_query(sqlalchemy.delete(self.table), *clauses, **filters)

        await self._connection.execute(query)

    async def list(
        self, *clauses, order_by: t.Optional[str] = None, order_direction: str = "asc", **filters
    ) -> t.AsyncIterable[dict[str, t.Any]]:
        """Lists all the elements in the table.

        If no elements are found, it returns an empty list. If no clauses or filters are given, it returns all the
        elements in the repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"].in_((1, 2, 3))`
        Order example: `order_by="id", order_direction="desc"`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param order_by: Column to order the elements.
        :param order_direction: Direction to order the elements, either `asc` or `desc`.
        :param filters: Filters to filter the elements.
        :return: Async iterable of the elements.
        """
        query = self._filter_query(sqlalchemy.select(self.table), *clauses, **filters)

        if order_by:
            query = query.order_by(
                self.table.c[order_by].desc() if order_direction == "desc" else self.table.c[order_by]
            )

        result = await self._connection.stream(query)

        async for row in result:
            yield dict[str, t.Any](row._asdict())

    async def drop(self, *clauses, **filters) -> int:
        """Drops elements in the table.

        Returns the number of elements dropped. If no clauses or filters are given, it deletes all the elements in the
        table.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"].in_((1, 2, 3))`
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

        Clause example: `table.c["id"].in_((1, 2, 3))`
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
    _table: t.ClassVar[sqlalchemy.Table]  # type: ignore

    def __init__(self, connection: AsyncConnection, *args, **kwargs):
        super().__init__(connection, *args, **kwargs)
        self._table_manager = SQLAlchemyTableManager(self._table, connection)

    def __eq__(self, other):
        return isinstance(other, SQLAlchemyTableRepository) and self._table == other._table and super().__eq__(other)

    async def create(self, *data: dict[str, t.Any]) -> list[dict[str, t.Any]]:
        """Creates new elements in the repository.

        If the element already exists, it raises an `exceptions.IntegrityError`. If the element is created, it returns
        the primary key of the element.

        :param data: The data to create the element.
        :return: The primary key of the created element.
        :raises IntegrityError: If the element already exists or cannot be inserted.
        """
        return await self._table_manager.create(*data)

    async def retrieve(self, *clauses, **filters) -> dict[str, t.Any]:
        """Retrieves an element from the repository.

        If the element does not exist, it raises a `NotFoundError`. If more than one element is found, it raises a
        `MultipleRecordsError`. If the element is found, it returns the element.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements
        using exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"].in_((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The element.
        :raises NotFoundError: If the element does not exist.
        :raises MultipleRecordsError: If more than one element is found.
        """
        return await self._table_manager.retrieve(*clauses, **filters)

    async def update(self, data: dict[str, t.Any], *clauses, **filters) -> list[dict[str, t.Any]]:
        """Updates an element in the repository.

        If the element does not exist, it raises a `NotFoundError`. If the element is updated, it returns the updated
        element.

        :param data: The data to update the element.
        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The updated elements.
        :raises IntegrityError: If the elements cannot be updated.
        """
        return await self._table_manager.update(data, *clauses, **filters)

    async def delete(self, *clauses, **filters) -> None:
        """Deletes an element from the repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements
        using exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"].in_((1, 2, 3))`
        Filter example: `id=1`

        :param id: The primary key of the element.
        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :raises NotFoundError: If the element does not exist.
        :raises MultipleRecordsError: If more than one element is found.
        """
        return await self._table_manager.delete(*clauses, **filters)

    def list(
        self, *clauses, order_by: t.Optional[str] = None, order_direction: str = "asc", **filters
    ) -> t.AsyncIterable[dict[str, t.Any]]:
        """Lists all the elements in the repository.

        Lists all the elements in the repository that match the clauses and filters. If no clauses or filters are given,
        it returns all the elements in the repository. If no elements are found, it returns an empty list.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"].in_((1, 2, 3))`
        Order example: `order_by="id", order_direction="desc"`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param order_by: Column to order the elements.
        :param order_direction: Direction to order the elements, either `asc` or `desc`.
        :param filters: Filters to filter the elements.
        :return: Async iterable of the elements.
        """
        return self._table_manager.list(*clauses, order_by=order_by, order_direction=order_direction, **filters)

    async def drop(self, *clauses, **filters) -> int:
        """Drops elements in the repository.

        Returns the number of elements dropped. If no clauses or filters are given, it deletes all the elements in the
        repository.

        Clauses are used to filter the elements using sqlalchemy clauses. Filters are used to filter the elements using
        exact values to specific columns. Clauses and filters can be combined.

        Clause example: `table.c["id"].in_((1, 2, 3))`
        Filter example: `id=1`

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The number of elements dropped.
        """
        return await self._table_manager.drop(*clauses, **filters)
