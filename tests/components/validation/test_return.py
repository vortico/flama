import marshmallow
import pytest
from starlette.testclient import TestClient

from flama.applications.flama import Flama
from flama.components import Component
from flama.endpoints import HTTPEndpoint
from flama.responses import HTMLResponse
from flama.types import http

# flake8: noqa


class Puppy:
    name = "Canna"


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


class BodyParam(marshmallow.Schema):
    name = marshmallow.fields.String()


class TestCaseReturnValidation:
    @pytest.fixture(
        scope="class", params=[pytest.param(True, id="endpoints"), pytest.param(False, id="function views")]
    )
    def app(self, request):
        app_ = Flama(components=[PuppyComponent()], schema=None, docs=None)

        if request.param:

            @app_.route("/return_string/")
            class FooEndpoint(HTTPEndpoint):
                def get(self, data: http.RequestData) -> str:
                    return "example content"

            @app_.route("/return_html/")
            class FooEndpoint(HTTPEndpoint):
                def get(self, data: http.RequestData) -> HTMLResponse:
                    return HTMLResponse("<html><body>example content</body></html>")

            @app_.route("/return_data/")
            class FooEndpoint(HTTPEndpoint):
                def get(self, data: http.RequestData) -> dict:
                    return {"example": "content"}

            @app_.route("/return_response/")
            class FooEndpoint(HTTPEndpoint):
                def get(self, data: http.RequestData) -> http.Response:
                    return http.JSONResponse({"example": "content"})

            @app_.route("/return_unserializable_json/")
            class FooEndpoint(HTTPEndpoint):
                def get(self) -> dict:
                    class Dummy:
                        pass

                    return {"dummy": Dummy()}

            @app_.route("/return-schema/", methods=["GET"])
            class ReturnSchemaHTTPEndpoint(HTTPEndpoint):
                async def get(self) -> BodyParam:
                    return {"name": "Canna"}

            @app_.route("/return-schema-many/", methods=["GET"])
            class ReturnSchemaManyHTTPEndpoint(HTTPEndpoint):
                async def get(self) -> BodyParam(many=True):
                    return [{"name": "Canna"}, {"name": "Sandy"}]

            @app_.route("/return-schema-empty/", methods=["GET"])
            class ReturnSchemaEmptyHTTPEndpoint(HTTPEndpoint):
                async def get(self) -> BodyParam:
                    return None

        else:

            @app_.route("/return_string/")
            def return_string(data: http.RequestData) -> str:
                return "example content"

            @app_.route("/return_html/")
            def return_html(data: http.RequestData) -> HTMLResponse:
                return HTMLResponse("<html><body>example content</body></html>")

            @app_.route("/return_data/")
            def return_data(data: http.RequestData) -> dict:
                return {"example": "content"}

            @app_.route("/return_response/")
            def return_response(data: http.RequestData) -> http.Response:
                return http.JSONResponse({"example": "content"})

            @app_.route("/return_unserializable_json/")
            def return_unserializable_json() -> dict:
                class Dummy:
                    pass

                return {"dummy": Dummy()}

            @app_.route("/return-schema/", methods=["GET"])
            async def return_schema() -> BodyParam:
                return {"name": "Canna"}

            @app_.route("/return-schema-many/", methods=["GET"])
            async def return_schema_many() -> BodyParam(many=True):
                return [{"name": "Canna"}, {"name": "Sandy"}]

            @app_.route("/return-schema-empty/", methods=["GET"])
            async def return_schema_empty() -> BodyParam:
                return None

        return app_

    @pytest.fixture(scope="function")
    def client(self, app):
        return TestClient(app)

    def test_return_string(self, client):
        response = client.get("/return_string/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == "example content"

    def test_return_html(self, client):
        response = client.get("/return_html/")
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert response.text == "<html><body>example content</body></html>"

    def test_return_data(self, client):
        response = client.get("/return_data/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"example": "content"}

    def test_return_response(self, client):
        response = client.get("/return_response/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"example": "content"}

    def test_return_unserializable_json(self, client):
        with pytest.raises(TypeError, match=r".*Object of type .?Dummy.? is not JSON serializable"):
            client.get("/return_unserializable_json/")

    def test_return_schema(self, client):
        response = client.get("/return-schema/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"name": "Canna"}

    def test_return_schema_many(self, client):
        response = client.get("/return-schema-many/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == [{"name": "Canna"}, {"name": "Sandy"}]

        response = client.get("/return-schema-str/")

    def test_return_schema_empty(self, client):
        response = client.get("/return-schema-empty/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == ""
