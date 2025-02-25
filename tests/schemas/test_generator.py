import contextlib
import typing as t
from collections import namedtuple

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields

from flama import schemas
from flama.endpoints import HTTPEndpoint
from flama.routing import Router
from flama.schemas import openapi
from flama.schemas.generator import SchemaRegistry
from tests.asserts import assert_recursive_contains


def _fix_ref(value, refs):
    try:
        prefix, name = value.rsplit("/", 1)
        return f"{prefix}/{refs[name]}"
    except KeyError:
        return value


def _replace_refs(schema, refs):
    if isinstance(schema, dict):
        return {k: _fix_ref(v, refs) if k == "$ref" else _replace_refs(v, refs) for k, v in schema.items()}

    if isinstance(schema, (list, tuple, set)):
        return [_replace_refs(x, refs) for x in schema]

    return schema


class TestCaseSchemaRegistry:
    @pytest.fixture(scope="function")
    def registry(self, app):
        return SchemaRegistry()

    @pytest.fixture(scope="function")
    def spec(self, openapi_spec):
        return openapi.OpenAPISpec.from_spec(openapi_spec)

    def test_empty_init(self):
        assert SchemaRegistry() == {}

    @pytest.mark.parametrize(
        ["operation", "register_schemas", "output"],
        [
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Foo",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/Foo")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Foo"],
                ["Foo"],
                id="response_reference",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/Bar")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="response_reference_nested",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/BarList")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="response_reference_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/BarDict")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="response_reference_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Foo",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"foo": {"$ref": "#!/components/schemas/Foo"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Foo"],
                ["Foo"],
                id="response_schema",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"bar": {"$ref": "#!/components/schemas/Bar"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="response_schema_nested",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="BarList",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"bar": {"$ref": "#!/components/schemas/BarList"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="response_schema_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="BarDict",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"bar": {"$ref": "#!/components/schemas/BarDict"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="response_schema_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Foo",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "foo": {
                                                        "type": "array",
                                                        "items": {"$ref": "#!/components/schemas/Foo"},
                                                    }
                                                },
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Foo"],
                ["Foo"],
                id="response_array",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Foo",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {"type": "object", "properties": {"foo": {"type": "foo"}}}
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                [],
                [],
                id="response_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/Foo"), responses=openapi.Responses({})
                ),
                ["Foo"],
                ["Foo"],
                id="body_reference",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/Bar"), responses=openapi.Responses({})
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="body_reference_nested",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/BarList"), responses=openapi.Responses({})
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="body_reference_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/BarDict"), responses=openapi.Responses({})
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="body_reference_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="Foo",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/Foo"}}}
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="body_schema",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="Bar",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/Bar"}}}
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="body_schema_nested",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="BarList",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/BarList"}}}
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="body_schema_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="BarDict",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/BarDict"}}}
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="body_schema_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="Foo",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {
                                        "type": "object",
                                        "properties": {
                                            "foo": {"type": "array", "items": {"$ref": "#!/components/schemas/Foo"}}
                                        },
                                    }
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="body_array",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="Foo",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema({"type": "object", "properties": {"foo": {"type": "foo"}}}),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                [],
                [],
                id="body_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/Foo")], responses=openapi.Responses({})
                ),
                ["Foo"],
                ["Foo"],
                id="parameter_reference",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/Bar")], responses=openapi.Responses({})
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="parameter_reference_nested",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/BarList")], responses=openapi.Responses({})
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="parameter_reference_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/BarDict")], responses=openapi.Responses({})
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="parameter_reference_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="foo",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/Foo"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="parameter_schema",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="bar",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"bar": {"$ref": "#!/components/schemas/Bar"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="parameter_schema_nested",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="bar",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"bar": {"$ref": "#!/components/schemas/BarList"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="parameter_schema_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="bar",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"bar": {"$ref": "#!/components/schemas/BarDict"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="parameter_schema_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="foo",
                            schema=openapi.Schema(
                                {
                                    "type": "object",
                                    "properties": {
                                        "foo": {"type": "array", "items": {"$ref": "#!/components/schemas/Foo"}}
                                    },
                                }
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="parameter_array",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="foo",
                            schema=openapi.Schema({"type": "object", "properties": {"foo": {"type": "foo"}}}),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                [],
                [],
                id="parameter_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/Foo")},
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="callback_reference",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/Bar")},
                    responses=openapi.Responses({}),
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="callback_reference_nested",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/BarList")},
                    responses=openapi.Responses({}),
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="callback_reference_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/BarDict")},
                    responses=openapi.Responses({}),
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="callback_reference_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="Foo",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "foo": {"$ref": "#!/components/schemas/Foo"}
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="callback_schema",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="Bar",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "bar": {"$ref": "#!/components/schemas/Bar"}
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="callback_schema_nested",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="BarList",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "bar": {"$ref": "#!/components/schemas/BarList"}
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="callback_schema_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="BarDict",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "bar": {"$ref": "#!/components/schemas/BarDict"}
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="callback_schema_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="Foo",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {"foo": {"type": "foo"}},
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                [],
                [],
                id="callback_wrong",
            ),
        ],
    )
    def test_used(self, registry, schemas, spec, operation, register_schemas, output):
        for schema in register_schemas:
            registry.register(schemas[schema].schema, name=schema)

        expected_output = {id(schemas[schema].schema) for schema in output}

        spec.add_path("/", openapi.Path(get=operation))

        assert set(registry.used(spec).keys()) == expected_output

    @pytest.mark.parametrize(
        ["schema", "explicit_name", "output"],
        [
            pytest.param("Foo", "Foo", {"Foo": "Foo"}, id="explicit_name"),
            pytest.param("Foo", None, {"Foo": None}, id="infer_name"),
            pytest.param("Bar", "Bar", {"Bar": "Bar"}, id="nested_schemas"),
        ],
    )
    def test_register(self, registry, schemas, schema, explicit_name, output):
        schema, name = schemas[schema]
        expected_name = name if not explicit_name else explicit_name
        exception = (
            contextlib.ExitStack() if expected_name else pytest.raises(ValueError, match="Cannot infer schema name.")
        )
        with exception:
            registry.register(schema, name=explicit_name)
            for s, n in output.items():
                assert schemas[s].schema in registry
                assert registry[schemas[s].schema].name == (n or schemas[s].name)

    def test_register_already_registered(self, registry, foo_schema):
        schema = foo_schema.schema
        registry.register(schema, name="Foo")
        with pytest.raises(ValueError, match="Schema is already registered."):
            registry.register(schema, name="Foo")

    @pytest.mark.parametrize(
        ["multiple", "result"],
        (
            pytest.param(
                False,
                openapi.Reference(ref="#/components/schemas/Foo"),
                id="schema",
            ),
            pytest.param(
                True,
                openapi.Schema({"type": "array", "items": {"$ref": "#/components/schemas/Foo"}}),
                id="array",
            ),
        ),
    )
    def test_get_openapi_ref(self, multiple, result, registry, foo_schema):
        schema = foo_schema.schema
        registry.register(schema, name="Foo")
        assert registry.get_openapi_ref(schema, multiple=multiple) == result


class TestCaseSchemaGenerator:
    @pytest.fixture(scope="function")
    def owner_schema(self, app):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model("Owner", name=(str, ...), __module__="pydantic.main")
            name = "pydantic.main.Owner"
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(title="Owner", fields={"name": typesystem.fields.String()})
            name = "typesystem.schemas.Owner"
        elif app.schema.schema_library.lib == marshmallow:
            schema = type("Owner", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
            name = "abc.Owner"
        else:
            raise ValueError("Wrong schema lib")
        return namedtuple("OwnerSchema", ("schema", "name"))(schema, name)

    @pytest.fixture(scope="function")
    def puppy_schema(self, app, owner_schema):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model(
                "Puppy", name=(str, ...), owner=(owner_schema.schema, ...), __module__="pydantic.main"
            )
            name = "pydantic.main.Puppy"
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(
                title="Puppy",
                fields={
                    "name": typesystem.fields.String(),
                    "owner": typesystem.Reference(
                        to="Owner", definitions=typesystem.Definitions({"Owner": owner_schema.schema})
                    ),
                },
            )
            name = "typesystem.schemas.Puppy"
        elif app.schema.schema_library.lib == marshmallow:
            schema = type(
                "Puppy",
                (marshmallow.Schema,),
                {
                    "name": marshmallow.fields.String(),
                    "owner": marshmallow.fields.Nested(owner_schema.schema),
                },
            )
            name = "abc.Puppy"
        else:
            raise ValueError("Wrong schema lib")
        return namedtuple("PuppySchema", ("schema", "name"))(schema, name)

    @pytest.fixture(scope="function")
    def body_param_schema(self, app):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model("BodyParam", name=(str, ...), __module__="pydantic.main")
            name = "pydantic.main.BodyParam"
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(title="BodyParam", fields={"name": typesystem.fields.String()})
            name = "typesystem.schemas.BodyParam"
        elif app.schema.schema_library.lib == marshmallow:
            schema = type("BodyParam", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
            name = "abc.BodyParam"
        else:
            raise ValueError("Wrong schema lib")
        return namedtuple("BodyParamSchema", ("schema", "name"))(schema, name)

    @pytest.fixture(scope="function")
    def schemas(self, owner_schema, puppy_schema, body_param_schema):
        return {"Owner": owner_schema, "Puppy": puppy_schema, "BodyParam": body_param_schema}

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, puppy_schema, body_param_schema):  # noqa: C901
        @app.route("/endpoint/", methods=["GET"])
        class PuppyEndpoint(HTTPEndpoint):
            async def get(self) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(puppy_schema.schema)]:
                """
                description: Endpoint.
                responses:
                  200:
                    description: Component.
                """
                return {"name": "Canna"}

        @app.route("/custom-component/", methods=["GET"])
        async def get() -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(puppy_schema.schema)]:
            """
            description: Custom component.
            responses:
              200:
                description: Component.
            """
            return {"name": "Canna"}

        @app.route("/many-components/", methods=["GET"])
        async def many_components() -> t.Annotated[
            list[schemas.SchemaType], schemas.SchemaMetadata(puppy_schema.schema)
        ]:
            """
            description: Many custom components.
            responses:
              200:
                description: Many components.
            """
            return [{"name": "foo"}, {"name": "bar"}]

        @app.route("/query-param/", methods=["GET"])
        async def query_param(param1: int, param2: t.Optional[str] = None, param3: bool = True):
            """
            description: Query param.
            responses:
              200:
                description: Param.
            """
            return {"name": param2}

        @app.route("/path-param/{param:int}/", methods=["GET"])
        async def path_param(param: int):
            """
            description: Path param.
            responses:
              200:
                description: Param.
            """
            return {"name": param}

        @app.route("/body-param/", methods=["POST"])
        async def body_param(param: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(body_param_schema.schema)]):
            """
            description: Body param.
            responses:
              200:
                description: Param.
            """
            return {"name": param["name"]}

        @app.route("/default-response/", methods=["GET"])
        async def default_response():
            """
            description: Default response.
            """
            return {"name": "Canna"}

        @app.route("/multiple-responses/", methods=["GET"])
        async def multiple_responses():
            """
            description: Multiple responses.
            responses:
              200:
                description: OK.
              400:
                description: Bad Request.
            """
            return {}

        @app.route("/custom-params/", methods=["GET"])
        async def custom_params(name: str):
            """
            description: Custom params.
            parameters:
              - in: query
                name: name
                schema:
                    type: string
                required: true
                description: The query param
            responses:
              200:
                description: OK.
            """
            return {}

        @app.route("/custom-body/", methods=["POST"])
        async def custom_body():
            """
            description: Custom body.
            requestBody:
                description: The body request
                required: true
                content:
                    multipart/form-data:
                        schema:
                            type: object
                            properties:
                                model:
                                    type: string
                                    format: binary
                                    description: The model file
                                name:
                                    type: string
                                    description: The model name
                                description:
                                    type: string
                                    description: The model description
            responses:
              200:
                description: OK.
            """
            return {}

        @app.route("/wrong-schema/", methods=["POST"])
        async def wrong():
            """
            Wrong schema.
            """
            return {}

        router = Router()
        router.add_route("/custom-component/", endpoint=get, methods=["GET"])
        app.mount("/mount", router)

        nested_router = Router()
        nested_router.add_route("/nested-component/", endpoint=get, methods=["GET"])
        mounted_router = Router()
        mounted_router.mount("/mount", nested_router)
        app.mount("/nested", mounted_router)

    def test_schema_info(self, app):
        schema = app.schema.schema["info"]

        assert schema["title"] == "Foo"
        assert schema["version"] == "1.0.0"
        assert schema["description"] == "Bar"

    def test_components_schemas(self, app, schemas):
        used_schemas = app.schema.schema["components"]["schemas"]

        # Check declared components are only those that are in use
        assert set(used_schemas.keys()) == {
            schemas["Owner"].name,
            schemas["Puppy"].name,
            schemas["BodyParam"].name,
            "flama.APIError",
        }

    @pytest.mark.parametrize(
        "path,verb,expected_schema",
        [
            pytest.param(
                "/query-param/",
                "get",
                {
                    "description": "Query param.",
                    "responses": {
                        "200": {"description": "Param."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                    "parameters": [
                        {
                            "name": "param1",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "param2",
                            "in": "query",
                            "required": False,
                            "schema": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        },
                        {
                            "name": "param3",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "boolean", "default": True},
                        },
                    ],
                },
                id="query_param",
            ),
            pytest.param(
                "/path-param/{param}/",
                "get",
                {
                    "description": "Path param.",
                    "responses": {
                        "200": {"description": "Param."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                    "parameters": [
                        {
                            "name": "param",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                },
                id="path_param",
            ),
            pytest.param(
                "/body-param/",
                "post",
                {
                    "description": "Body param.",
                    "responses": {
                        "200": {"description": "Param."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/BodyParam"}}}
                    },
                },
                id="body_param",
            ),
            pytest.param(
                "/custom-component/",
                "get",
                {
                    "description": "Custom component.",
                    "responses": {
                        "200": {
                            "description": "Component.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_single",
            ),
            pytest.param(
                "/many-components/",
                "get",
                {
                    "description": "Many custom components.",
                    "responses": {
                        "200": {
                            "description": "Many components.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_multiple",
            ),
            pytest.param(
                "/endpoint/",
                "get",
                {
                    "description": "Endpoint.",
                    "responses": {
                        "200": {
                            "description": "Component.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_endpoint",
            ),
            pytest.param(
                "/mount/custom-component/",
                "get",
                {
                    "description": "Custom component.",
                    "responses": {
                        "200": {
                            "description": "Component.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_mount",
            ),
            pytest.param(
                "/nested/mount/nested-component/",
                "get",
                {
                    "description": "Custom component.",
                    "responses": {
                        "200": {
                            "description": "Component.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_nested_mount",
            ),
            pytest.param(
                "/default-response/",
                "get",
                {
                    "description": "Default response.",
                    "responses": {
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        }
                    },
                },
                id="default_response_schema",
            ),
            pytest.param(
                "/multiple-responses/",
                "get",
                {
                    "description": "Multiple responses.",
                    "responses": {
                        "200": {"description": "OK."},
                        "400": {"description": "Bad Request."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                },
                id="multiple_responses",
            ),
            pytest.param(
                "/custom-params/",
                "get",
                {
                    "description": "Custom params.",
                    "parameters": [
                        {
                            "in": "query",
                            "name": "name",
                            "schema": {"type": "string"},
                            "required": True,
                            "description": "The query param",
                        }
                    ],
                    "responses": {
                        "200": {"description": "OK."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                },
                id="custom_params",
            ),
            pytest.param(
                "/custom-body/",
                "post",
                {
                    "description": "Custom body.",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "model": {
                                            "type": "string",
                                            "format": "binary",
                                            "description": "The model file",
                                        },
                                        "name": {"type": "string", "description": "The model name"},
                                        "description": {"type": "string", "description": "The model description"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "OK."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.APIError"}}
                            },
                        },
                    },
                },
                id="custom_body",
            ),
            pytest.param(
                "/wrong-schema/",
                "post",
                {},
                id="wrong_schema",
            ),
        ],
    )
    def test_schema(self, app, schemas, path, verb, expected_schema):
        schema = _replace_refs(expected_schema, {k: v.name for k, v in schemas.items()})

        assert_recursive_contains(schema, app.schema.schema["paths"][path][verb])
