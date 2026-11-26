from collections import namedtuple

import marshmallow
import pydantic
import pytest

from flama.schemas.libs._libraries import libraries


@pytest.fixture(scope="function")
def llm_schema(app, request):
    """Resolve a built-in LLM schema, named as ``flama.<module>.<schema>``, from the default schema library.

    Bound via ``indirect`` so each ``TestCase<Schema>`` selects its subject once with
    ``@pytest.mark.parametrize("llm_schema", [...], indirect=True)``. Depends on ``app`` so the default schema library
    is pinned before the lookup.
    """
    _, module, name = request.param.split(".")
    return getattr(getattr(libraries.default.schemas, module), name)


@pytest.fixture(scope="function")
def foo_schema(app):
    if libraries.default.name == "pydantic":
        schema = pydantic.create_model("Foo", name=(str, ...), __module__="pydantic.main")
        name = "pydantic.main.Foo"
    elif libraries.default.name == "marshmallow":
        schema = type("Foo", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
        name = "abc.Foo"
    else:
        raise ValueError(f"Wrong schema lib: {libraries.default.name}")
    return namedtuple("FooSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if libraries.default.name == "pydantic":
        schema = pydantic.create_model("Bar", foo=(child_schema, ...), __module__="pydantic.main")
        name = "pydantic.main.Bar"
    elif libraries.default.name == "marshmallow":
        schema = type("Bar", (marshmallow.Schema,), {"foo": marshmallow.fields.Nested(child_schema())})
        name = "abc.Bar"
    else:
        raise ValueError(f"Wrong schema lib: {libraries.default.name}")
    return namedtuple("BarSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_optional_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if libraries.default.name == "pydantic":
        schema = pydantic.create_model("BarOptional", foo=(child_schema | None, None), __module__="pydantic.main")
        name = "pydantic.main.BarOptional"
    elif libraries.default.name == "marshmallow":
        schema = type(
            "BarOptional",
            (marshmallow.Schema,),
            {"foo": marshmallow.fields.Nested(child_schema(), required=False, dump_default=None, allow_none=True)},
        )
        name = "abc.BarOptional"
    else:
        raise ValueError(f"Wrong schema lib: {libraries.default.name}")
    return namedtuple("BarOptionalSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_multiple_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if libraries.default.name == "pydantic":
        schema = pydantic.create_model(
            "BarMultiple", first=(child_schema, ...), second=(child_schema, ...), __module__="pydantic.main"
        )
        name = "pydantic.main.BarMultiple"
    elif libraries.default.name == "marshmallow":
        schema = type(
            "BarMultiple",
            (marshmallow.Schema,),
            {"first": marshmallow.fields.Nested(child_schema()), "second": marshmallow.fields.Nested(child_schema())},
        )
        name = "abc.BarMultiple"
    else:
        raise ValueError(f"Wrong schema lib: {libraries.default.name}")
    return namedtuple("BarMultipleSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_list_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if libraries.default.name == "pydantic":
        schema = pydantic.create_model("BarList", foo=(list[child_schema], ...), __module__="pydantic.main")
        name = "pydantic.main.BarList"
    elif libraries.default.name == "marshmallow":
        schema = type(
            "BarList",
            (marshmallow.Schema,),
            {"foo": marshmallow.fields.List(marshmallow.fields.Nested(child_schema()))},
        )
        name = "abc.BarList"
    else:
        raise ValueError(f"Wrong schema lib: {libraries.default.name}")
    return namedtuple("BarListSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_dict_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if libraries.default.name == "pydantic":
        schema = pydantic.create_model("BarDict", foo=(dict[str, child_schema], ...), __module__="pydantic.main")
        name = "pydantic.main.BarDict"
    elif libraries.default.name == "marshmallow":
        schema = type(
            "BarDict",
            (marshmallow.Schema,),
            {"foo": marshmallow.fields.Dict(values=marshmallow.fields.Nested(child_schema()))},
        )
        name = "abc.BarDict"
    else:
        raise ValueError(f"Wrong schema lib: {libraries.default.name}")
    return namedtuple("BarDictSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def foobar_nested_schema(app, bar_schema):
    child_schema = bar_schema.schema
    if libraries.default.name == "pydantic":
        schema = pydantic.create_model("FooBarNested", foobar=(child_schema, ...), __module__="pydantic.main")
        name = "pydantic.main.FooBarNested"
    elif libraries.default.name == "marshmallow":
        schema = type(
            "FooBarNested",
            (marshmallow.Schema,),
            {"foobar": marshmallow.fields.Nested(child_schema())},
        )
        name = "abc.FooBarNested"
    else:
        raise ValueError(f"Wrong schema lib: {libraries.default.name}")
    return namedtuple("FooBarNestedSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def schemas(
    foo_schema,
    bar_schema,
    bar_optional_schema,
    bar_multiple_schema,
    bar_list_schema,
    bar_dict_schema,
    foobar_nested_schema,
):
    return {
        "Foo": foo_schema,
        "Bar": bar_schema,
        "BarOptional": bar_optional_schema,
        "BarMultiple": bar_multiple_schema,
        "BarList": bar_list_schema,
        "BarDict": bar_dict_schema,
        "FooBarNested": foobar_nested_schema,
    }
