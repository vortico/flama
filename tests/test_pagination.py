import typing as t
from collections import namedtuple

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields
from pytest import param

from flama import schemas
from flama.pagination import paginator
from tests.asserts import assert_recursive_contains


@pytest.fixture(scope="function")
def app(app):
    paginator.schemas = {}
    return app


@pytest.fixture(scope="function")
def output_schema(app):
    if app.schema.schema_library.lib == pydantic:
        schema = pydantic.create_model("OutputSchema", value=(t.Optional[int], ...), __module__="pydantic.main")
        name = "pydantic.main.OutputSchema"
    elif app.schema.schema_library.lib == typesystem:
        schema = typesystem.Schema(title="OutputSchema", fields={"value": typesystem.fields.Integer(allow_null=True)})
        name = "typesystem.schemas.OutputSchema"
    elif app.schema.schema_library.lib == marshmallow:
        schema = type("OutputSchema", (marshmallow.Schema,), {"value": marshmallow.fields.Integer(allow_none=True)})
        name = "abc.OutputSchema"
    else:
        raise ValueError(f"Wrong schema lib: {app.schema.schema_library.lib}")

    return namedtuple("OutputSchema", ("schema", "name"))(schema=schema, name=name)


class TestCasePageNumberPagination:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, output_schema):
        @app.route("/page-number/", methods=["GET"], pagination="page_number")
        def page_number(
            **kwargs,
        ) -> t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(output_schema.schema)]:
            return [{"value": i} for i in range(25)]

    def test_registered_schemas(self, app, output_schema):
        schemas = app.schema.schema["components"]["schemas"]
        name_prefix = output_schema.name.rsplit(".", 1)[0]

        assert set(schemas.keys()) == {
            f"{name_prefix}.OutputSchema",
            f"{name_prefix}.PageNumberPaginatedOutputSchema",
            "flama.PageNumberMeta",
            "flama.APIError",
        }

    def test_invalid_view(self, output_schema):
        with pytest.raises(TypeError, match=r"Paginated views must define \*\*kwargs param"):

            @paginator._paginate_page_number
            def invalid() -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(output_schema.schema)]: ...

    def test_invalid_response(self):
        with pytest.raises(ValueError, match=r"Wrong schema type"):

            @paginator._paginate_page_number
            def invalid(): ...

    def test_pagination_schema_parameters(self, app):
        schema = app.schema.schema["paths"]["/page-number/"]["get"]
        parameters = schema.get("parameters", [])

        assert_recursive_contains(
            {
                "name": "count",
                "in": "query",
                "required": False,
                "schema": {"anyOf": [{"type": "boolean"}, {"type": "null"}], "default": False},
            },
            parameters[0],
        )
        assert_recursive_contains(
            {
                "name": "page",
                "in": "query",
                "required": False,
                "schema": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
            parameters[1],
        )
        assert_recursive_contains(
            {
                "name": "page_size",
                "in": "query",
                "required": False,
                "schema": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
            parameters[2],
        )

    def test_pagination_schema_return(self, app, output_schema):
        prefix, name = output_schema.name.rsplit(".", 1)
        paginated_output_schema_name = f"{prefix}.PageNumberPaginated{name}"
        response_schema = app.schema.schema["paths"]["/page-number/"]["get"]["responses"]["200"]
        component_schema = app.schema.schema["components"]["schemas"][paginated_output_schema_name]

        assert "data" in component_schema["properties"]
        assert component_schema["properties"]["data"]["items"] == {"$ref": f"#/components/schemas/{output_schema.name}"}
        assert component_schema["properties"]["data"]["type"] == "array"
        assert set(component_schema["required"]) == {"meta", "data"}
        assert component_schema["type"] == "object"

        assert response_schema == {
            "description": "Description not provided.",
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{paginated_output_schema_name}"},
                }
            },
        }

    async def test_async_function(self, app, client, output_schema):
        @app.route("/page-number-async/", methods=["GET"], pagination="page_number")
        async def page_number_async(
            **kwargs,
        ) -> t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(output_schema.schema)]:
            return [{"value": i} for i in range(25)]

        response = await client.get("/page-number-async/")
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "meta": {"page": 1, "page_size": 10, "count": None},
            "data": [{"value": i} for i in range(10)],
        }

    @pytest.mark.parametrize(
        "params,status_code,expected",
        (
            param(
                {},
                200,
                {"meta": {"page_size": 10, "page": 1, "count": None}, "data": [{"value": i} for i in range(10)]},
                id="default_params",
            ),
            param(
                {"page_size": 5},
                200,
                {"meta": {"page_size": 5, "page": 1, "count": None}, "data": [{"value": i} for i in range(5)]},
                id="explicit_page_size",
            ),
            param(
                {"page": 2},
                200,
                {"meta": {"page_size": 10, "page": 2, "count": None}, "data": [{"value": i} for i in range(10, 20)]},
                id="explicit_page",
            ),
            param(
                {"page": 4, "page_size": 5},
                200,
                {"meta": {"page_size": 5, "page": 4, "count": None}, "data": [{"value": i} for i in range(15, 20)]},
                id="explicit_page_and_page_size",
            ),
            param(
                {"count": True},
                200,
                {"meta": {"page_size": 10, "page": 1, "count": 25}, "data": [{"value": i} for i in range(10)]},
                id="count",
            ),
        ),
    )
    async def test_params(self, client, params, status_code, expected):
        response = await client.get("/page-number/", params=params)
        assert response.status_code == status_code, response.json()
        assert response.json() == expected


class TestCaseLimitOffsetPagination:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, output_schema):
        @app.route("/limit-offset/", methods=["GET"], pagination="limit_offset")
        def limit_offset(
            **kwargs,
        ) -> t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(output_schema.schema)]:
            return [{"value": i} for i in range(25)]

    def test_registered_schemas(self, app, output_schema):
        schemas = app.schema.schema["components"]["schemas"]
        name_prefix = output_schema.name.rsplit(".", 1)[0]

        assert set(schemas.keys()) == {
            f"{name_prefix}.OutputSchema",
            f"{name_prefix}.LimitOffsetPaginatedOutputSchema",
            "flama.LimitOffsetMeta",
            "flama.APIError",
        }

    def test_invalid_view(self, output_schema):
        with pytest.raises(TypeError, match=r"Paginated views must define \*\*kwargs param"):

            @paginator._paginate_limit_offset
            def invalid() -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(output_schema.schema)]: ...

    def test_invalid_response(self):
        with pytest.raises(ValueError, match=r"Wrong schema type"):

            @paginator._paginate_limit_offset
            def invalid(): ...

    def test_pagination_schema_parameters(self, app):
        schema = app.schema.schema["paths"]["/limit-offset/"]["get"]
        parameters = schema.get("parameters", [])

        assert_recursive_contains(
            {
                "name": "count",
                "in": "query",
                "required": False,
                "schema": {"anyOf": [{"type": "boolean"}, {"type": "null"}], "default": False},
            },
            parameters[0],
        )
        assert_recursive_contains(
            {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
            parameters[1],
        )
        assert_recursive_contains(
            {
                "name": "offset",
                "in": "query",
                "required": False,
                "schema": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
            parameters[2],
        )

    def test_pagination_schema_return(self, app, output_schema):
        prefix, name = output_schema.name.rsplit(".", 1)
        paginated_output_schema_name = f"{prefix}.LimitOffsetPaginated{name}"

        response_schema = app.schema.schema["paths"]["/limit-offset/"]["get"]["responses"]["200"]
        component_schema = app.schema.schema["components"]["schemas"][paginated_output_schema_name]

        assert "data" in component_schema["properties"]
        assert component_schema["properties"]["data"]["items"] == {"$ref": f"#/components/schemas/{output_schema.name}"}
        assert component_schema["properties"]["data"]["type"] == "array"
        assert set(component_schema["required"]) == {"meta", "data"}
        assert component_schema["type"] == "object"

        assert response_schema == {
            "description": "Description not provided.",
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{paginated_output_schema_name}"},
                }
            },
        }

    async def test_async_function(self, app, client, output_schema):
        @app.route("/limit-offset-async/", methods=["GET"], pagination="limit_offset")
        async def limit_offset_async(
            **kwargs,
        ) -> t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(output_schema.schema)]:
            return [{"value": i} for i in range(25)]

        response = await client.get("/limit-offset-async/")
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "meta": {"limit": 10, "offset": 0, "count": None},
            "data": [{"value": i} for i in range(10)],
        }

    @pytest.mark.parametrize(
        "params,status_code,expected",
        (
            param(
                {},
                200,
                {"meta": {"limit": 10, "offset": 0, "count": None}, "data": [{"value": i} for i in range(10)]},
                id="default_params",
            ),
            param(
                {"limit": 5},
                200,
                {"meta": {"limit": 5, "offset": 0, "count": None}, "data": [{"value": i} for i in range(5)]},
                id="explicit_limit",
            ),
            param(
                {"offset": 5},
                200,
                {"meta": {"limit": 10, "offset": 5, "count": None}, "data": [{"value": i} for i in range(5, 15)]},
                id="explicit_offset",
            ),
            param(
                {"offset": 5, "limit": 20},
                200,
                {"meta": {"limit": 20, "offset": 5, "count": None}, "data": [{"value": i} for i in range(5, 25)]},
                id="explicit_offset_and_limit",
            ),
            param(
                {"count": True},
                200,
                {"meta": {"limit": 10, "offset": 0, "count": 25}, "data": [{"value": i} for i in range(10)]},
                id="count",
            ),
        ),
    )
    async def test_params(self, client, params, status_code, expected):
        response = await client.get("/limit-offset/", params=params)
        assert response.status_code == status_code, response.json()
        assert response.json() == expected
