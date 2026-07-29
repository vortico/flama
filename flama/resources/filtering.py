import dataclasses
import datetime
import decimal
import inspect
import typing as t

from flama import exceptions
from flama.resources.exceptions import ResourceFilterInvalid
from flama.schemas.data_structures import Field, Schema
from flama.schemas.exceptions import SchemaValidationError

try:
    import sqlalchemy
except Exception:  # pragma: no cover
    raise exceptions.DependencyNotInstalled(
        dependency=exceptions.DependencyNotInstalled.Dependency.sqlalchemy, dependant=__name__
    )

__all__ = ["Operator", "OPERATORS", "Filter", "Filters"]

_ORDERED: tuple[type, ...] = (int, float, decimal.Decimal, datetime.date, datetime.datetime, datetime.time, str)
_TEXT: tuple[type, ...] = (str,)
_NEGATION = "not:"


@dataclasses.dataclass(frozen=True)
class Operator:
    """One way of comparing a column against what a request asked of it.

    :param name: Name the operator is written under, as the prefix of a filter value.
    :param clause: Builds the SQLAlchemy clause comparing a column against a value.
    :param types: Types the operator can compare, or ``None`` when it can compare any.
    :param value: Whether the operator is written with a value after its name.
    :param aggregate: Whether every value written for it makes one clause rather than one each.
    """

    name: str
    clause: t.Callable[[t.Any, t.Any], t.Any] = dataclasses.field(repr=False)
    types: tuple[type, ...] | None = None
    value: bool = True
    aggregate: bool = False

    def applies_to(self, type_: type) -> bool:
        """Whether this operator can compare a column of the given type.

        :param type_: Type held by the column.
        :return: True if the comparison is meaningful for that type.
        """
        return self.types is None or issubclass(type_, self.types)


OPERATORS: dict[str, Operator] = {
    operator.name: operator
    for operator in (
        Operator("eq", lambda c, v: c == v),
        Operator("gt", lambda c, v: c > v, types=_ORDERED),
        Operator("gte", lambda c, v: c >= v, types=_ORDERED),
        Operator("lt", lambda c, v: c < v, types=_ORDERED),
        Operator("lte", lambda c, v: c <= v, types=_ORDERED),
        Operator("in", lambda c, v: c.in_(v), aggregate=True),
        Operator("isnull", lambda c, v: c.is_(None), value=False),
        # Escaped, so that a value holding a wildcard finds the rows holding that character rather than
        # standing for any run of them. A caller who means a pattern writes `like` instead.
        Operator("contains", lambda c, v: c.contains(v, autoescape=True), types=_TEXT),
        Operator("startswith", lambda c, v: c.startswith(v, autoescape=True), types=_TEXT),
        Operator("endswith", lambda c, v: c.endswith(v, autoescape=True), types=_TEXT),
        Operator("icontains", lambda c, v: c.icontains(v, autoescape=True), types=_TEXT),
        Operator("istartswith", lambda c, v: c.istartswith(v, autoescape=True), types=_TEXT),
        Operator("iendswith", lambda c, v: c.iendswith(v, autoescape=True), types=_TEXT),
        Operator("like", lambda c, v: c.like(v), types=_TEXT),
        Operator("ilike", lambda c, v: c.ilike(v), types=_TEXT),
    )
}


@dataclasses.dataclass(frozen=True)
class Filter:
    """A column a collection can be filtered by, and the operators it answers.

    :param column: Column being filtered.
    :param operators: Operators the column answers, in the order they were granted.
    """

    # Compared by name rather than by identity, since comparing two columns builds a clause saying they
    # hold the same value instead of answering whether they are the same column.
    column: t.Any = dataclasses.field(compare=False)
    operators: tuple[Operator, ...]
    name: str = dataclasses.field(init=False)
    schema: Schema = dataclasses.field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.column.name)
        # Built once here rather than per request, since coercing a value needs nothing that a request
        # carries, only the type the column holds.
        object.__setattr__(
            self, "schema", Schema.build(name="Filter", fields=[Field(self.name, self.column.type.python_type)])
        )

    def clauses(self, values: list[str]) -> list[t.Any]:
        """Read what a request asked of this column into the clauses expressing it.

        :param values: Values written for this column, one per time it was named.
        :return: One clause per condition asked, which the caller combines.
        :raises ValidationError: If a value names an operator this column does not answer, or does not
            hold what the column does.
        """
        parsed = [self._parse(value) for value in values]
        # An aggregating operator offers its values as alternatives to one another, so all of them make
        # a single clause. Read one at a time they would instead ask for a row holding every one at once.
        aggregated: dict[tuple[str, bool], list[t.Any]] = {}
        clauses = []

        for operator, negated, value in parsed:
            if operator.aggregate:
                aggregated.setdefault((operator.name, negated), []).append(value)
            else:
                clauses.append(self._clause(operator, negated, value))

        clauses.extend(
            self._clause(OPERATORS[name], negated, values_) for (name, negated), values_ in aggregated.items()
        )

        return clauses

    def _parse(self, value: str) -> tuple[Operator, bool, t.Any]:
        negated = value.startswith(_NEGATION)
        name, separator, remainder = value.removeprefix(_NEGATION).partition(":")

        if (operator := OPERATORS.get(name)) is None:
            # Nothing an operator is named after, so the value is what it looks like, and equality is
            # what a value on its own asks for.
            return OPERATORS["eq"], negated, self._value(value.removeprefix(_NEGATION))

        if operator not in self.operators:
            expected = ", ".join(f"'{granted.name}'" for granted in self.operators)
            raise exceptions.ValidationError(
                detail={self.name: [f"Operator '{name}' is not available, expected one of: {expected}."]}
            )

        if operator.value and not separator:
            raise exceptions.ValidationError(detail={self.name: [f"Operator '{name}' expects a value."]})

        if not operator.value and separator:
            raise exceptions.ValidationError(detail={self.name: [f"Operator '{name}' expects no value."]})

        return operator, negated, self._value(remainder) if operator.value else None

    def _value(self, raw: str) -> t.Any:
        try:
            return self.schema.validate({self.name: raw})[self.name]
        except SchemaValidationError as e:
            raise exceptions.ValidationError(detail=e.errors)

    def _clause(self, operator: Operator, negated: bool, value: t.Any) -> t.Any:
        clause = operator.clause(self.column, value)

        return sqlalchemy.not_(clause) if negated else clause


@dataclasses.dataclass(frozen=True)
class Filters:
    """The columns a collection can be filtered by.

    :param filters: Filters, by the name of the column each reads.
    """

    filters: dict[str, Filter]

    @classmethod
    def build(cls, name: str, model: t.Any, declaration: t.Any = None) -> "Filters":
        """Read a resource's filter declaration into the surface it describes.

        Declaring nothing asks for equality on every column a query string can carry, which is what a
        collection offers when its author has expressed no interest in the question. Declaring a sequence
        of names narrows that to those columns, and declaring a mapping grants each of them the operators
        it is worth answering.

        :param name: Resource class name, used to qualify error messages.
        :param model: Resource model.
        :param declaration: Columns to filter by, alone or each with the operators it answers.
        :return: The filterable surface.
        :raises ResourceFilterInvalid: If a declared column is not part of the model or cannot be carried
            by a query string, or an operator cannot compare what the column holds.
        """
        if declaration is None:
            # The primary key is served by the retrieve route, so a collection filtered by it answers a
            # question that was already asked better elsewhere.
            return cls(
                filters={
                    column.name: Filter(column, (OPERATORS["eq"],))
                    for column in model.table.columns
                    if column.name != model.primary_key.name and cls._is_filterable(column)
                }
            )

        granted = declaration if isinstance(declaration, dict) else {column: ("eq",) for column in declaration}
        filters = {}

        for column_name, operator_names in granted.items():
            try:
                column = model.table.columns[column_name]
            except KeyError:
                raise ResourceFilterInvalid(name, column_name, "it is not a column of the model") from None

            if not cls._is_filterable(column):
                raise ResourceFilterInvalid(name, column_name, "a query string cannot carry what it holds")

            operators = []
            for operator_name in operator_names:
                if (operator := OPERATORS.get(operator_name)) is None:
                    raise ResourceFilterInvalid(name, column_name, f"there is no operator '{operator_name}'")

                if not operator.applies_to(column.type.python_type):
                    raise ResourceFilterInvalid(
                        name, column_name, f"operator '{operator_name}' cannot compare what it holds"
                    )

                operators.append(operator)

            filters[column_name] = Filter(column, tuple(operators))

        return cls(filters=filters)

    def parameters(self, exclude: t.Container[str] = ()) -> list[inspect.Parameter]:
        """The parameters carrying these filters on a handler's signature.

        Every filter is read as text, whatever the column holds, because the value carries the operator
        alongside it, and repeated, because naming a column more than once is how several conditions are
        asked of it at once.

        :param exclude: Names already spoken for, which cannot be told apart from a filter in a query
            string and are therefore left out.
        :return: One parameter per filter, in declaration order.
        """
        return [
            # Positional-or-keyword to match the parameters the paginator appends after these.
            inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=list[str] | None)
            for name in self.filters
            if name not in exclude
        ]

    def clauses(self, values: dict[str, t.Any]) -> list[t.Any]:
        """Read what a request asked of a collection into the clauses expressing it.

        :param values: Values written for each filter, by column name.
        :return: Clauses to narrow the collection by, which the repository combines.
        """
        return [
            clause
            for name, filter_ in self.filters.items()
            if values.get(name) is not None
            for clause in filter_.clauses(values[name])
        ]

    @staticmethod
    def _is_filterable(column: t.Any) -> bool:
        try:
            # Read as a value, since the column type is only known at runtime.
            return Field.is_http_valid_type(t.cast("type", column.type.python_type) | None)
        except NotImplementedError:  # A column type naming no Python equivalent, as a custom one may not.
            return False
