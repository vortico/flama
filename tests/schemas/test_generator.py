import typing as t

import marshmallow
import pydantic
import pytest
import typesystem

from flama.endpoints import HTTPEndpoint
from flama.routing import Router
from flama.schemas import openapi
from flama.schemas.generator import SchemaRegistry
from tests.asserts import assert_recursive_contains


class TestCaseSchemaRegistry:
    @pytest.fixture(scope="function")
    def registry(self):
        return SchemaRegistry()

    @pytest.fixture(scope="function")
    def foo_schema(self, registry):
        from flama import schemas

        if schemas.lib == pydantic:
            schema = pydantic.create_model("Foo", name=(str, ...))
        elif schemas.lib == typesystem:
            schema = typesystem.Schema(fields={"name": typesystem.fields.String()})
        elif schemas.lib == marshmallow:
            schema = type("Foo", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
        else:
            raise ValueError("Wrong schema lib")
        registry.register(schema, "Foo")
        return schema

    @pytest.fixture(scope="function")
    def foo_array_schema(self, foo_schema):
        return t.List[foo_schema]

    @pytest.fixture(scope="function")
    def spec(self):
        return openapi.OpenAPISpec(title="Foo", version="1.0.0")

    def test_empty_init(self):
        assert SchemaRegistry() == {}

    @pytest.mark.parametrize(
        "operation,output",
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
                True,
                id="response_reference",
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
                True,
                id="response_schema",
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
                True,
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
                False,
                id="response_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/Foo"), responses=openapi.Responses({})
                ),
                True,
                id="body_reference",
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
                True,
                id="body_schema",
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
                True,
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
                False,
                id="body_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/Foo")], responses=openapi.Responses({})
                ),
                True,
                id="parameter_reference",
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
                True,
                id="parameter_schema",
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
                True,
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
                False,
                id="parameter_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/Foo")},
                    responses=openapi.Responses({}),
                ),
                True,
                id="callback_reference",
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
                True,
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
                False,
                id="callback_wrong",
            ),
        ],
    )
    def test_used(self, registry, foo_schema, spec, operation, output):
        expected_output = {id(foo_schema): registry[foo_schema]} if output else {}
        spec.add_path("/", openapi.Path(get=operation))
        assert registry.used(spec) == expected_output

    @pytest.mark.parametrize(
        "schema,name,exception",
        [
            pytest.param(typesystem.Schema(fields={}), "Foo", None, id="typesystem_explicit_name"),
            pytest.param(
                typesystem.Schema(fields={}),
                None,
                ValueError("Cannot infer schema name."),
                id="typesystem_cannot_infer_name",
            ),
            pytest.param(type("Foo", (marshmallow.Schema,), {}), None, None, id="marshmallow_infer_name"),
        ],
        indirect=["exception"],
    )
    def test_register(self, registry, schema, name, exception):
        with exception:
            registry.register(schema, name=name)
            assert registry[schema].name == "Foo"

    def test_register_already_registered(self, registry, foo_schema):
        with pytest.raises(ValueError, match="Schema is already registered."):
            registry.register(foo_schema, name="Foo")

    @pytest.mark.parametrize(
        ["multiple", "result"],
        (
            pytest.param(False, openapi.Reference(ref="#/components/schemas/Foo"), id="single"),
            pytest.param(
                True,
                openapi.Schema({"type": "array", "items": openapi.Reference(ref="#/components/schemas/Foo")}),
                id="multiple",
            ),
        ),
    )
    def test_get_openapi_ref_single(self, multiple, result, registry, foo_schema):
        assert registry.get_openapi_ref(foo_schema, multiple=multiple) == result


class TestCaseSchemaGenerator:
    @pytest.fixture(scope="function")
    def owner_schema(self, app):
        from flama import schemas

        if schemas.lib == pydantic:
            schema = pydantic.create_model("Owner", name=(str, ...))
        elif schemas.lib == typesystem:
            schema = typesystem.Schema(fields={"name": typesystem.fields.String()})
        elif schemas.lib == marshmallow:
            schema = type("Owner", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
        else:
            raise ValueError("Wrong schema lib")
        app.schema.schemas["Owner"] = schema
        return schema

    @pytest.fixture(scope="function")
    def puppy_schema(self, app, owner_schema):
        from flama import schemas

        if schemas.lib == pydantic:
            schema = pydantic.create_model("Puppy", name=(str, ...), owner=(owner_schema, ...))
        elif schemas.lib == typesystem:
            schema = typesystem.Schema(
                fields={
                    "name": typesystem.fields.String(),
                    "owner": typesystem.Reference(to="Owner", definitions=app.schema.schemas),
                }
            )
        elif schemas.lib == marshmallow:
            schema = type(
                "Puppy",
                (marshmallow.Schema,),
                {
                    "name": marshmallow.fields.String(),
                    "owner": marshmallow.fields.Nested(owner_schema),
                },
            )
        else:
            raise ValueError("Wrong schema lib")
        app.schema.schemas["Puppy"] = schema
        return schema

    @pytest.fixture(scope="function")
    def puppy_array_schema(self, app, puppy_schema):
        return t.List[puppy_schema]

    @pytest.fixture(scope="function")
    def body_param_schema(self, app):
        from flama import schemas

        if schemas.lib == pydantic:
            schema = pydantic.create_model("BodyParam", name=(str, ...))
        elif schemas.lib == typesystem:
            schema = typesystem.Schema(fields={"name": typesystem.fields.String()})
        elif schemas.lib == marshmallow:
            schema = type("BodyParam", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
        else:
            raise ValueError("Wrong schema lib")

        app.schema.schemas["BodyParam"] = schema
        return schema

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, puppy_schema, puppy_array_schema, body_param_schema):
        @app.route("/endpoint/", methods=["GET"])
        class PuppyEndpoint(HTTPEndpoint):
            async def get(self) -> puppy_schema:
                """
                description: Endpoint.
                responses:
                  200:
                    description: Component.
                """
                return {"name": "Canna"}

        @app.route("/custom-component/", methods=["GET"])
        async def get() -> puppy_schema:
            """
            description: Custom component.
            responses:
              200:
                description: Component.
            """
            return {"name": "Canna"}

        @app.route("/many-components/", methods=["GET"])
        async def many_components() -> puppy_array_schema:
            """
            description: Many custom components.
            responses:
              200:
                description: Many components.
            """
            return [{"name": "foo"}, {"name": "bar"}]

        @app.route("/query-param/", methods=["GET"])
        async def query_param(param1: int, param2: str = None, param3: bool = True):
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
        async def body_param(param: body_param_schema):
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
        assert schema["version"] == "0.1"
        assert schema["description"] == "Bar"

    def test_components_schemas(self, app):
        schemas = app.schema.schema["components"]["schemas"]

        # Check declared components are only those that are in use
        assert set(schemas.keys()) == {"Owner", "Puppy", "BodyParam", "APIError"}

    @pytest.mark.parametrize(
        "path,verb,expected_schema",
        [
            pytest.param(
                "/query-param/",
                "get",
                {
                    "description": "Query param.",
                    "responses": {"200": {"description": "Param."}},
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
                            "schema": {"type": ["string", "null"]},
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
                    "responses": {"200": {"description": "Param."}},
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
                    "responses": {"200": {"description": "Param."}},
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
                        }
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
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "items": {"$ref": "#/components/schemas/Puppy"},
                                        "type": "array",
                                    }
                                }
                            },
                        }
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
                        }
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
                        }
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
                        }
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
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/APIError"}}},
                        }
                    },
                },
                id="default_response_schema",
            ),
        ],
    )
    def test_schema(self, app, path, verb, expected_schema):
        assert_recursive_contains(expected_schema, app.schema.schema["paths"][path][verb])
