import marshmallow
import pytest
import typesystem
from pytest import param

from flama.pagination import paginator


@pytest.fixture(scope="function")
def output_schema(app):
    from flama import schemas

    if schemas.lib == typesystem:
        schema = typesystem.Schema(fields={"value": typesystem.fields.Integer(allow_null=True)})
    elif schemas.lib == marshmallow:
        schema = type("OutputSchema", (marshmallow.Schema,), {"value": marshmallow.fields.Integer(allow_none=True)})
    else:
        raise ValueError("Wrong schema lib")

    app.schema.schemas["OutputSchema"] = schema
    return schema


class TestPageNumberResponse:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, output_schema):
        @app.route("/page-number/", methods=["GET"])
        @paginator.page_number(schema_name="OutputSchema")
        def page_number(**kwargs) -> output_schema:
            return [{"value": i} for i in range(25)]

    def test_registered_schemas(self, app):
        schemas = app.schema.schema["components"]["schemas"]

        assert set(schemas.keys()) == {"OutputSchema", "PageNumberPaginatedOutputSchema", "PageNumberMeta", "APIError"}

    def test_invalid_view(self):
        with pytest.raises(TypeError, match=r"Paginated views must define \*\*kwargs param"):

            @paginator.page_number(schema_name="OutputSchema")
            def invalid():
                ...

    def test_pagination_schema_parameters(self, app):
        schema = app.schema.schema["paths"]["/page-number/"]["get"]
        parameters = schema.get("parameters", {})

        assert parameters == [
            {"name": "page", "in": "query", "required": False, "schema": {"type": ["integer", "null"]}},
            {"name": "page_size", "in": "query", "required": False, "schema": {"type": ["integer", "null"]}},
            {"name": "count", "in": "query", "required": False, "schema": {"type": "boolean", "default": True}},
        ]

    def test_pagination_schema_return(self, app):
        response_schema = app.schema.schema["paths"]["/page-number/"]["get"]["responses"]["200"]
        component_schema = app.schema.schema["components"]["schemas"]["PageNumberPaginatedOutputSchema"]

        assert "data" in component_schema["properties"]
        assert component_schema["properties"]["data"]["items"] == {"$ref": "#/components/schemas/OutputSchema"}
        assert component_schema["properties"]["data"]["type"] == "array"
        assert set(component_schema["required"]) == {"meta", "data"}
        assert component_schema["type"] == "object"

        assert response_schema == {
            "description": "Description not provided.",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/PageNumberPaginatedOutputSchema"}},
            },
        }

    def test_async_function(self, app, client, output_schema):
        @app.route("/page-number-async/", methods=["GET"])
        @paginator.page_number(schema_name="OutputSchema")
        async def page_number_async(**kwargs) -> output_schema:
            return [{"value": i} for i in range(25)]

        response = client.get("/page-number-async/")
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "meta": {"page": 1, "page_size": 10, "count": 25},
            "data": [{"value": i} for i in range(10)],
        }

    @pytest.mark.parametrize(
        "params,status_code,expected",
        (
            param(
                {},
                200,
                {"meta": {"page_size": 10, "page": 1, "count": 25}, "data": [{"value": i} for i in range(10)]},
                id="default_params",
            ),
            param(
                {"page_size": 5},
                200,
                {"meta": {"page_size": 5, "page": 1, "count": 25}, "data": [{"value": i} for i in range(5)]},
                id="explicit_page_size",
            ),
            param(
                {"page": 2},
                200,
                {"meta": {"page_size": 10, "page": 2, "count": 25}, "data": [{"value": i} for i in range(10, 20)]},
                id="explicit_page",
            ),
            param(
                {"page": 4, "page_size": 5},
                200,
                {"meta": {"page_size": 5, "page": 4, "count": 25}, "data": [{"value": i} for i in range(15, 20)]},
                id="explicit_page_and_page_size",
            ),
            param(
                {"count": False},
                200,
                {"meta": {"page_size": 10, "page": 1, "count": None}, "data": [{"value": i} for i in range(10)]},
                id="no_count",
            ),
        ),
    )
    def test_params(self, client, params, status_code, expected):
        response = client.get("/page-number/", params=params)
        assert response.status_code == status_code, response.json()
        assert response.json() == expected


class TestLimitOffsetResponse:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, output_schema):
        @app.route("/limit-offset/", methods=["GET"])
        @paginator.limit_offset(schema_name="OutputSchema")
        def limit_offset(**kwargs) -> output_schema:
            return [{"value": i} for i in range(25)]

    def test_registered_schemas(self, app):
        schemas = app.schema.schema["components"]["schemas"]

        assert set(schemas.keys()) == {
            "OutputSchema",
            "LimitOffsetPaginatedOutputSchema",
            "LimitOffsetMeta",
            "APIError",
        }

    def test_invalid_view(self, app):
        with pytest.raises(TypeError, match=r"Paginated views must define \*\*kwargs param"):

            @paginator.limit_offset(schema_name="Foo")
            def invalid():
                ...

    def test_pagination_schema_parameters(self, app):
        schema = app.schema.schema["paths"]["/limit-offset/"]["get"]
        parameters = schema.get("parameters", {})

        assert parameters == [
            {"name": "limit", "in": "query", "required": False, "schema": {"type": ["integer", "null"]}},
            {"name": "offset", "in": "query", "required": False, "schema": {"type": ["integer", "null"]}},
            {"name": "count", "in": "query", "required": False, "schema": {"type": "boolean", "default": True}},
        ]

    def test_pagination_schema_return(self, app):
        response_schema = app.schema.schema["paths"]["/limit-offset/"]["get"]["responses"]["200"]
        component_schema = app.schema.schema["components"]["schemas"]["LimitOffsetPaginatedOutputSchema"]

        assert "data" in component_schema["properties"]
        assert component_schema["properties"]["data"]["items"] == {"$ref": "#/components/schemas/OutputSchema"}
        assert component_schema["properties"]["data"]["type"] == "array"
        assert set(component_schema["required"]) == {"meta", "data"}
        assert component_schema["type"] == "object"

        assert response_schema == {
            "description": "Description not provided.",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/LimitOffsetPaginatedOutputSchema"}}
            },
        }

    def test_async_function(self, app, client, output_schema):
        @app.route("/limit-offset-async/", methods=["GET"])
        @paginator.limit_offset(schema_name="OutputSchema")
        async def limit_offset_async(**kwargs) -> output_schema:
            return [{"value": i} for i in range(25)]

        response = client.get("/limit-offset-async/")
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "meta": {"limit": 10, "offset": 0, "count": 25},
            "data": [{"value": i} for i in range(10)],
        }

    @pytest.mark.parametrize(
        "params,status_code,expected",
        (
            param(
                {},
                200,
                {"meta": {"limit": 10, "offset": 0, "count": 25}, "data": [{"value": i} for i in range(10)]},
                id="default_params",
            ),
            param(
                {"limit": 5},
                200,
                {"meta": {"limit": 5, "offset": 0, "count": 25}, "data": [{"value": i} for i in range(5)]},
                id="explicit_limit",
            ),
            param(
                {"offset": 5},
                200,
                {"meta": {"limit": 10, "offset": 5, "count": 25}, "data": [{"value": i} for i in range(5, 15)]},
                id="explicit_offset",
            ),
            param(
                {"offset": 5, "limit": 20},
                200,
                {"meta": {"limit": 20, "offset": 5, "count": 25}, "data": [{"value": i} for i in range(5, 25)]},
                id="explicit_offset_and_limit",
            ),
            param(
                {"count": False},
                200,
                {"meta": {"limit": 10, "offset": 0, "count": None}, "data": [{"value": i} for i in range(10)]},
                id="no_count",
            ),
        ),
    )
    def test_params(self, client, params, status_code, expected):
        response = client.get("/limit-offset/", params=params)
        assert response.status_code == status_code, response.json()
        assert response.json() == expected
