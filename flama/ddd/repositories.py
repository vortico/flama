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


__all__ = ["AbstractRepository", "SQLAlchemyRepository"]


class AbstractRepository(abc.ABC):
    ...


class SQLAlchemyRepository(AbstractRepository):
    _table: t.ClassVar[sqlalchemy.Table]

    def __init__(self, connection: "AsyncConnection"):
        self._connection = connection

    def __eq__(self, other):
        return (
            isinstance(other, SQLAlchemyRepository)
            and self._table == other._table
            and self._connection == other._connection
        )

    @property
    def primary_key(self) -> sqlalchemy.Column:
        """Returns the primary key of the model.

        :return: sqlalchemy.Column: The primary key of the model.
        :raises: exceptions.IntegrityError: If the model has a composed primary key.
        """
        model_pk_columns = list(sqlalchemy.inspect(self._table).primary_key.columns.values())

        if len(model_pk_columns) != 1:
            raise exceptions.IntegrityError("Composed primary keys are not supported")

        return model_pk_columns[0]

    async def create(self, data: t.Union[t.Dict[str, t.Any], types.Schema]) -> t.Optional[t.Tuple[t.Any, ...]]:
        """Creates a new element in the repository.

        :param data: The data to create the element.
        :return: The primary key of the created element.
        :raises: exceptions.IntegrityError: If the element already exists.
        """
        try:
            result = await self._connection.execute(sqlalchemy.insert(self._table).values(**data))
        except sqlalchemy.exc.IntegrityError as e:
            raise exceptions.IntegrityError(str(e))
        return tuple(result.inserted_primary_key) if result.inserted_primary_key else None

    async def retrieve(self, id_: t.Any) -> types.Schema:
        """Retrieves an element from the repository.

        :param id_: The primary key of the element.
        :return: The element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        element = (
            await self._connection.execute(
                sqlalchemy.select(self._table).where(self._table.c[self.primary_key.name] == id_)
            )
        ).first()

        if element is None:
            raise exceptions.NotFoundError(str(id_))

        return types.Schema(element._asdict())

    async def update(self, id_: t.Any, data: types.Schema) -> types.Schema:
        """Updates an element in the repository.

        :param id_: The primary key of the element.
        :param data: The data to update the element.
        :return: The updated element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        pk = self.primary_key
        result = await self._connection.execute(
            sqlalchemy.update(self._table).where(self._table.c[pk.name] == id_).values(**data)
        )
        if result.rowcount == 0:
            raise exceptions.NotFoundError(id_)
        return types.Schema({pk.name: id_, **data})

    async def delete(self, id_: t.Any) -> None:
        """Deletes an element from the repository.

        :param id_: The primary key of the element.
        :raises: exceptions.NotFoundError: If the element does not exist.
        """
        result = await self._connection.execute(
            sqlalchemy.delete(self._table).where(self._table.c[self.primary_key.name] == id_)
        )
        if result.rowcount == 0:
            raise exceptions.NotFoundError(id_)

    async def list(self, *clauses, **filters) -> t.List[types.Schema]:
        """Lists all the elements in the repository.

        :param clauses: Clauses to filter the elements.
        :param filters: Filters to filter the elements.
        :return: The elements.
        """
        query = sqlalchemy.select(self._table)
        where_clauses = tuple(clauses) + tuple(self._table.c[k] == v for k, v in filters.items())
        if where_clauses:
            query = query.where(sqlalchemy.and_(*where_clauses))
        return [types.Schema(row._asdict()) async for row in await self._connection.stream(query)]

    async def drop(self) -> int:
        """Drops all the elements in the repository.

        :return: The number of elements dropped.
        """
        result = await self._connection.execute(sqlalchemy.delete(self._table))
        return result.rowcount
