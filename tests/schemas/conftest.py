import typing as t
from collections import namedtuple

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields


@pytest.fixture(scope="function")
def foo_schema(app):
    if app.schema.schema_library.lib == pydantic:
        schema = pydantic.create_model("Foo", name=(str, ...), __module__="pydantic.main")
        name = "pydantic.main.Foo"
    elif app.schema.schema_library.lib == typesystem:
        schema = typesystem.Schema(title="Foo", fields={"name": typesystem.fields.String()})
        name = "typesystem.schemas.Foo"
    elif app.schema.schema_library.lib == marshmallow:
        schema = type("Foo", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
        name = "abc.Foo"
    else:
        raise ValueError(f"Wrong schema lib: {app.schema.schema_library.lib}")
    return namedtuple("FooSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if app.schema.schema_library.lib == pydantic:
        schema = pydantic.create_model("Bar", foo=(child_schema, ...), __module__="pydantic.main")
        name = "pydantic.main.Bar"
    elif app.schema.schema_library.lib == typesystem:
        schema = typesystem.Schema(
            title="Bar",
            fields={"foo": typesystem.Reference(to="Foo", definitions=typesystem.Definitions({"Foo": child_schema}))},
        )
        name = "typesystem.schemas.Bar"
    elif app.schema.schema_library.lib == marshmallow:
        schema = type("Bar", (marshmallow.Schema,), {"foo": marshmallow.fields.Nested(child_schema())})
        name = "abc.Bar"
    else:
        raise ValueError(f"Wrong schema lib: {app.schema.schema_library.lib}")
    return namedtuple("BarSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_optional_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if app.schema.schema_library.lib == pydantic:
        schema = pydantic.create_model(
            "BarOptional", foo=(t.Union[child_schema, None], None), __module__="pydantic.main"
        )
        name = "pydantic.main.BarOptional"
    elif app.schema.schema_library.lib == typesystem:
        schema = typesystem.Schema(
            title="BarOptional",
            fields={
                "foo": typesystem.Reference(
                    to="Foo", definitions=typesystem.Definitions({"Foo": child_schema}), allow_null=True, default=None
                )
            },
        )
        name = "typesystem.schemas.BarOptional"
    elif app.schema.schema_library.lib == marshmallow:
        schema = type(
            "BarOptional",
            (marshmallow.Schema,),
            {"foo": marshmallow.fields.Nested(child_schema(), required=False, dump_default=None, allow_none=True)},
        )
        name = "abc.BarOptional"
    else:
        raise ValueError(f"Wrong schema lib: {app.schema.schema_library.lib}")
    return namedtuple("BarOptionalSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_list_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if app.schema.schema_library.lib == pydantic:
        schema = pydantic.create_model("BarList", foo=(list[child_schema], ...), __module__="pydantic.main")
        name = "pydantic.main.BarList"
    elif app.schema.schema_library.lib == typesystem:
        schema = typesystem.Schema(
            title="BarList",
            fields={
                "foo": typesystem.Array(
                    typesystem.Reference(to="Foo", definitions=typesystem.Definitions({"Foo": child_schema}))
                )
            },
        )
        name = "typesystem.schemas.BarList"
    elif app.schema.schema_library.lib == marshmallow:
        schema = type(
            "BarList",
            (marshmallow.Schema,),
            {"foo": marshmallow.fields.List(marshmallow.fields.Nested(child_schema()))},
        )
        name = "abc.BarList"
    else:
        raise ValueError(f"Wrong schema lib: {app.schema.schema_library.lib}")
    return namedtuple("BarListSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def bar_dict_schema(app, foo_schema):
    child_schema = foo_schema.schema
    if app.schema.schema_library.lib == pydantic:
        schema = pydantic.create_model("BarDict", foo=(dict[str, child_schema], ...), __module__="pydantic.main")
        name = "pydantic.main.BarDict"
    elif app.schema.schema_library.lib == typesystem:
        schema = typesystem.Schema(
            title="BarDict",
            fields={
                "foo": typesystem.Object(
                    properties=typesystem.Reference(to="Foo", definitions=typesystem.Definitions({"Foo": child_schema}))
                )
            },
        )
        name = "typesystem.schemas.BarDict"
    elif app.schema.schema_library.lib == marshmallow:
        schema = type(
            "BarDict",
            (marshmallow.Schema,),
            {"foo": marshmallow.fields.Dict(values=marshmallow.fields.Nested(child_schema()))},
        )
        name = "abc.BarDict"
    else:
        raise ValueError(f"Wrong schema lib: {app.schema.schema_library.lib}")
    return namedtuple("BarDictSchema", ("schema", "name"))(schema=schema, name=name)


@pytest.fixture(scope="function")
def schemas(foo_schema, bar_schema, bar_list_schema, bar_dict_schema):
    return {"Foo": foo_schema, "Bar": bar_schema, "BarList": bar_list_schema, "BarDict": bar_dict_schema}
