import datetime

import pytest
import sqlalchemy

from flama.exceptions import ValidationError
from flama.resources import data_structures
from flama.resources.exceptions import ResourceFilterInvalid
from flama.resources.filtering import OPERATORS, Filter, Filters


@pytest.fixture(scope="function")
def table():
    return sqlalchemy.Table(
        "gadget",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("name", sqlalchemy.String),
        sqlalchemy.Column("age", sqlalchemy.Integer),
        sqlalchemy.Column("born", sqlalchemy.Date),
        sqlalchemy.Column("payload", sqlalchemy.JSON),
    )


@pytest.fixture(scope="function")
def model(table):
    return data_structures.Model(table=table, primary_key=data_structures.PrimaryKey("id", int))


@pytest.fixture(scope="function")
def sql():
    """Read clauses as the SQL they stand for, so a test asserts on what is asked of the database."""
    return lambda clauses: [str(clause.compile(compile_kwargs={"literal_binds": True})) for clause in clauses]


class TestCaseOperator:
    @pytest.mark.parametrize(
        ["operator", "type_", "expected"],
        [
            pytest.param("eq", int, True, id="any_type"),
            pytest.param("gte", int, True, id="ordered_type"),
            pytest.param("gte", datetime.date, True, id="ordered_date"),
            pytest.param("contains", str, True, id="text_type"),
            pytest.param("contains", int, False, id="text_operator_on_a_number"),
        ],
    )
    def test_applies_to(self, operator, type_, expected):
        assert OPERATORS[operator].applies_to(type_) == expected


class TestCaseFilter:
    @pytest.mark.parametrize(
        ["column", "granted", "values", "expected", "exception"],
        [
            # A value written alone asks for equality, which is the point of not having to say so.
            pytest.param("age", ("eq",), ["18"], ["gadget.age = 18"], None, id="bare_value"),
            pytest.param("age", ("eq",), ["eq:18"], ["gadget.age = 18"], None, id="equality_named"),
            pytest.param("age", ("gte",), ["gte:18"], ["gadget.age >= 18"], None, id="operator"),
            # Naming a column twice narrows it, which is how a range is asked for.
            pytest.param(
                "age",
                ("gte", "lte"),
                ["gte:18", "lte:65"],
                ["gadget.age >= 18", "gadget.age <= 65"],
                None,
                id="range",
            ),
            pytest.param("age", ("eq",), ["not:eq:18"], ["gadget.age != 18"], None, id="negated"),
            pytest.param("age", ("isnull",), ["isnull"], ["gadget.age IS NULL"], None, id="null"),
            pytest.param("age", ("isnull",), ["not:isnull"], ["gadget.age IS NOT NULL"], None, id="not_null"),
            # Every value written for an aggregating operator belongs to one clause, since they are
            # offered as alternatives rather than asked for at once.
            pytest.param("age", ("in",), ["in:1", "in:2"], ["gadget.age IN (1, 2)"], None, id="membership"),
            pytest.param(
                "age", ("in",), ["not:in:1", "not:in:2"], ["(gadget.age NOT IN (1, 2))"], None, id="negated_membership"
            ),
            # A wildcard in the value finds the rows holding that character, not any run of characters.
            pytest.param(
                "name",
                ("contains",),
                ["contains:50%"],
                ["gadget.name LIKE '%' || '50/%' || '%' ESCAPE '/'"],
                None,
                id="pattern_escaped",
            ),
            # Unless a pattern is what was meant, which is what `like` is for.
            pytest.param("name", ("like",), ["like:50%"], ["gadget.name LIKE '50%'"], None, id="pattern_literal"),
            # Only a name an operator answers to splits a value, so most text needs no escaping at all.
            pytest.param(
                "name",
                ("eq",),
                ["https://example.com"],
                ["gadget.name = 'https://example.com'"],
                None,
                id="unknown_prefix_is_the_value",
            ),
            # And a value whose prefix does name one is written literally by naming equality explicitly.
            pytest.param(
                "name", ("eq",), ["eq:in:stock"], ["gadget.name = 'in:stock'"], None, id="prefix_escaped_by_equality"
            ),
            pytest.param(
                "age",
                ("eq",),
                ["gte:18"],
                None,
                ValidationError({"age": ["Operator 'gte' is not available, expected one of: 'eq'."]}),
                id="operator_not_granted",
            ),
            pytest.param(
                "age",
                ("gte",),
                ["gte"],
                None,
                ValidationError({"age": ["Operator 'gte' expects a value."]}),
                id="value_missing",
            ),
            pytest.param(
                "age",
                ("isnull",),
                ["isnull:true"],
                None,
                ValidationError({"age": ["Operator 'isnull' expects no value."]}),
                id="value_unexpected",
            ),
            pytest.param("age", ("eq",), ["nope"], None, ValidationError, id="value_the_column_cannot_hold"),
        ],
        indirect=["exception"],
    )
    def test_clauses(self, table, sql, column, granted, values, expected, exception):
        filter_ = Filter(table.columns[column], tuple(OPERATORS[name] for name in granted))

        with exception:
            assert sql(filter_.clauses(values)) == expected


class TestCaseFilters:
    @pytest.mark.parametrize(
        ["declaration", "expected", "exception"],
        [
            # Declaring nothing asks for equality on every column a query string can carry, but the key,
            # which the retrieve route already serves, and `payload`, which no query string can hold.
            pytest.param(None, {"name": ("eq",), "age": ("eq",), "born": ("eq",)}, None, id="default"),
            pytest.param(("name", "age"), {"name": ("eq",), "age": ("eq",)}, None, id="sequence"),
            pytest.param(
                {"name": ("eq", "contains"), "age": ("gte",)},
                {"name": ("eq", "contains"), "age": ("gte",)},
                None,
                id="mapping",
            ),
            # The key is not offered by default, but asking for it explicitly is not a mistake.
            pytest.param(("id",), {"id": ("eq",)}, None, id="primary_key"),
            pytest.param(
                ("nope",),
                None,
                ResourceFilterInvalid("Gadget", "nope", "it is not a column of the model"),
                id="unknown_column",
            ),
            pytest.param(
                ("payload",),
                None,
                ResourceFilterInvalid("Gadget", "payload", "a query string cannot carry what it holds"),
                id="column_not_carriable",
            ),
            pytest.param(
                {"name": ("nope",)},
                None,
                ResourceFilterInvalid("Gadget", "name", "there is no operator 'nope'"),
                id="unknown_operator",
            ),
            pytest.param(
                {"age": ("contains",)},
                None,
                ResourceFilterInvalid("Gadget", "age", "operator 'contains' cannot compare what it holds"),
                id="operator_not_applicable",
            ),
        ],
        indirect=["exception"],
    )
    def test_build(self, model, declaration, expected, exception):
        with exception:
            filters = Filters.build("Gadget", model, declaration)

            assert {name: tuple(o.name for o in f.operators) for name, f in filters.filters.items()} == expected

    @pytest.mark.parametrize(
        ["exclude", "expected"],
        [
            pytest.param((), ["name", "age", "born"], id="all"),
            # A name already spoken for cannot be told apart from a filter in a query string.
            pytest.param({"age"}, ["name", "born"], id="excluded"),
        ],
    )
    def test_parameters(self, model, exclude, expected):
        parameters = Filters.build("Gadget", model).parameters(exclude=exclude)

        # Every filter is read as repeated text, since the value carries the operator alongside it.
        assert [(p.name, p.annotation, p.default) for p in parameters] == [
            (name, list[str] | None, None) for name in expected
        ]

    @pytest.mark.parametrize(
        ["values", "expected"],
        [
            pytest.param(
                {"name": ["ana"], "age": ["gte:18", "lte:65"], "born": None},
                ["gadget.name = 'ana'", "gadget.age >= 18", "gadget.age <= 65"],
                id="across_columns",
            ),
            pytest.param({"name": None, "age": None}, [], id="nothing_asked"),
        ],
    )
    def test_clauses(self, model, sql, values, expected):
        filters = Filters.build("Gadget", model, {"name": ("eq",), "age": ("gte", "lte")})

        assert sql(filters.clauses(values)) == expected
