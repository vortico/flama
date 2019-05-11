from unittest.mock import call, mock_open, patch

import marshmallow
import pytest
from starlette.testclient import TestClient

from flama.applications.flama import Flama
from flama.endpoints import HTTPEndpoint
from flama.routing import Router


class Puppy(marshmallow.Schema):
    name = marshmallow.fields.String()


class BodyParam(marshmallow.Schema):
    name = marshmallow.fields.String()


class TestCaseSchema:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Flama(
            components=[],
            title="Foo",
            version="0.1",
            description="Bar",
            schema="/schema/",
            docs="/docs/",
            redoc="/redoc/",
        )

        @app_.route("/endpoint/", methods=["GET"])
        class PuppyEndpoint(HTTPEndpoint):
            async def get(self) -> Puppy:
                """
                description: Custom component.
                responses:
                  200:
                    description: Component.
                """
                return {"name": "Canna"}

        @app_.route("/custom-component/", methods=["GET"])
        async def get(self) -> Puppy:
            """
            description: Custom component.
            responses:
              200:
                description: Component.
            """
            return {"name": "Canna"}

        @app_.route("/many-custom-component/", methods=["GET"])
        async def many_custom_component() -> Puppy(many=True):
            """
            description: Many custom component.
            responses:
              200:
                description: Components.
            """
            return [{"name": "Canna"}, {"name": "Sandy"}]

        @app_.route("/query-param/", methods=["GET"])
        async def query_param(param: str = "Foo"):
            """
            description: Query param.
            responses:
              200:
                description: Param.
            """
            return {"name": param}

        @app_.route("/path-param/{param:int}/", methods=["GET"])
        async def path_param(param: int):
            """
            description: Path param.
            responses:
              200:
                description: Param.
            """
            return {"name": param}

        @app_.route("/body-param/", methods=["POST"])
        async def body_param(param: BodyParam):
            """
            description: Body param.
            responses:
              200:
                description: Param.
            """
            return {"name": param["name"]}

        @app_.route("/default-response/", methods=["GET"])
        async def default_response():
            """
            description: Default response.
            """
            return {"name": "Canna"}

        router = Router()
        router.add_route("/custom-component/", endpoint=get, methods=["GET"])
        app_.mount("/mount", router)

        return app_

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_schema_info(self, app):
        schema = app.schema["info"]

        assert schema["title"] == "Foo"
        assert schema["version"] == "0.1"
        assert schema["description"] == "Bar"

    def test_schema_query_params(self, app):
        schema = app.schema["paths"]["/query-param/"]["get"]
        parameters = schema.get("parameters", {})
        response = schema.get("responses", {}).get(200, {})

        assert schema["description"] == "Query param."
        assert response == {"description": "Param."}
        assert parameters == [
            {"name": "param", "in": "query", "required": False, "schema": {"type": "string", "default": "Foo"}}
        ]

    def test_schema_path_params(self, app):
        schema = app.schema["paths"]["/path-param/{param}/"]["get"]
        parameters = schema.get("parameters", {})
        response = schema.get("responses", {}).get(200, {})

        assert schema["description"] == "Path param."
        assert response == {"description": "Param."}
        assert parameters == [
            {"name": "param", "in": "path", "required": True, "schema": {"type": "integer", "format": "int32"}}
        ]

    def test_schema_body_params(self, app):
        schema = app.schema["paths"]["/body-param/"]["post"]
        parameters = schema.get("parameters")
        response = schema.get("responses", {}).get(200, {})
        body = schema.get("requestBody", {})

        assert schema["description"] == "Body param."
        assert response == {"description": "Param."}
        assert parameters is None
        assert body == {
            "content": {"application/json": {"schema": {"type": "object", "properties": {"name": {"type": "string"}}}}}
        }

    def test_schema_output_schema(self, app):
        schema = app.schema["paths"]["/custom-component/"]["get"]
        response = schema.get("responses", {}).get(200, {})

        assert schema["description"] == "Custom component."
        assert response == {
            "description": "Component.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
        }

    def test_schema_output_schema_many(self, app):
        schema = app.schema["paths"]["/many-custom-component/"]["get"]
        parameters = schema.get("parameters")
        response = schema.get("responses", {}).get(200, {})

        assert schema["description"] == "Many custom component."
        assert parameters is None
        assert response == {
            "description": "Components.",
            "content": {
                "application/json": {"schema": {"items": {"$ref": "#/components/schemas/Puppy"}, "type": "array"}}
            },
        }

    def test_schema_output_schema_using_endpoint(self, app):
        schema = app.schema["paths"]["/endpoint/"]["get"]
        parameters = schema.get("parameters")
        response = schema.get("responses", {}).get(200, {})

        assert schema["description"] == "Custom component."
        assert parameters is None
        assert response == {
            "description": "Component.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
        }

    def test_schema_output_schema_using_mount(self, app):
        schema = app.schema["paths"]["/mount/custom-component/"]["get"]
        parameters = schema.get("parameters")
        response = schema.get("responses", {}).get(200, {})

        assert schema["description"] == "Custom component."
        assert parameters is None
        assert response == {
            "description": "Component.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
        }

    def test_schema_default_response(self, app):
        schema = app.schema["paths"]["/default-response/"]["get"]
        parameters = schema.get("parameters")
        response = schema.get("responses", {}).get("default", {})

        assert schema["description"] == "Default response."
        assert parameters is None
        assert response == {
            "description": "Unexpected error.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/APIError"}}},
        }

    def test_view_schema(self, client):
        response = client.get("/schema/")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/vnd.oai.openapi"

    def test_view_docs(self, client):
        with patch("flama.applications.schema.Template") as mock_template, patch(
            "flama.applications.schema.open", mock_open(read_data="foo")
        ) as file_mock:
            mock_template.return_value.substitute.return_value = "bar"
            response = client.get("/docs/")

        assert response.status_code == 200
        assert file_mock.call_count == 1
        assert file_mock.call_args_list[0][0][0].endswith("flama/templates/swagger_ui.html")
        assert mock_template.call_args_list == [call("foo")]
        assert response.content == b"bar"

    def test_view_redoc(self, client):
        with patch("flama.applications.schema.Template") as mock_template, patch(
            "flama.applications.schema.open", mock_open(read_data="foo")
        ) as file_mock:
            mock_template.return_value.substitute.return_value = "bar"
            response = client.get("/redoc/")

        assert response.status_code == 200
        assert file_mock.call_count == 1
        assert file_mock.call_args_list[0][0][0].endswith("flama/templates/redoc.html")
        assert mock_template.call_args_list == [call("foo")]
        assert response.content == b"bar"
