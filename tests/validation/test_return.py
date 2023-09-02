import marshmallow
import pytest

from flama import Component, endpoints, http, types
from flama.applications import Flama
from flama.client import AsyncClient


class Puppy:
    name = "Canna"


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


class BodyParam(marshmallow.Schema):
    name = marshmallow.fields.String()


class TestCaseReturnValidation:
    @pytest.fixture(  # noqa: C901
        scope="class", params=[pytest.param(True, id="endpoints"), pytest.param(False, id="function views")]
    )
    def app(self, request):  # noqa: C901
        app_ = Flama(components=[PuppyComponent()], schema=None, docs=None)

        if request.param:

            @app_.route("/return_string/")
            class StrEndpoint(endpoints.HTTPEndpoint):
                def get(self, data: types.RequestData) -> str:
                    return "example content"

            @app_.route("/return_html/")
            class HTMLEndpoint(endpoints.HTTPEndpoint):
                def get(self, data: types.RequestData) -> http.HTMLResponse:
                    return http.HTMLResponse("<html><body>example content</body></html>")

            @app_.route("/return_data/")
            class DictEndpoint(endpoints.HTTPEndpoint):
                def get(self, data: types.RequestData) -> dict:
                    return {"example": "content"}

            @app_.route("/return_response/")
            class JSONEndpoint(endpoints.HTTPEndpoint):
                def get(self, data: types.RequestData) -> http.JSONResponse:
                    return http.JSONResponse({"example": "content"})

            @app_.route("/return_unserializable_json/")
            class UnserializableEndpoint(endpoints.HTTPEndpoint):
                def get(self) -> dict:
                    class Dummy:
                        pass

                    return {"dummy": Dummy()}

            @app_.route("/return-schema/", methods=["GET"])
            class ReturnSchemaHTTPEndpoint(endpoints.HTTPEndpoint):
                async def get(self) -> BodyParam:
                    return {"name": "Canna"}

            @app_.route("/return-schema-many/", methods=["GET"])
            class ReturnSchemaManyHTTPEndpoint(endpoints.HTTPEndpoint):
                async def get(self) -> BodyParam(many=True):
                    return [{"name": "Canna"}, {"name": "Sandy"}]

            @app_.route("/return-schema-empty/", methods=["GET"])
            class ReturnSchemaEmptyHTTPEndpoint(endpoints.HTTPEndpoint):
                async def get(self) -> BodyParam:
                    return None

        else:

            @app_.route("/return_string/")
            def return_string(data: types.RequestData) -> str:
                return "example content"

            @app_.route("/return_html/")
            def return_html(data: types.RequestData) -> http.HTMLResponse:
                return http.HTMLResponse("<html><body>example content</body></html>")

            @app_.route("/return_data/")
            def return_data(data: types.RequestData) -> dict:
                return {"example": "content"}

            @app_.route("/return_response/")
            def return_response(data: types.RequestData) -> http.Response:
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
    async def client(self, app):
        async with AsyncClient(app=app) as client:
            yield client

    async def test_return_string(self, client):
        response = await client.get("/return_string/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == "example content"

    async def test_return_html(self, client):
        response = await client.get("/return_html/")
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert response.text == "<html><body>example content</body></html>"

    async def test_return_data(self, client):
        response = await client.get("/return_data/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"example": "content"}

    async def test_return_response(self, client):
        response = await client.get("/return_response/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"example": "content"}

    async def test_return_unserializable_json(self, client):
        with pytest.raises(TypeError, match=r".*Object of type .?Dummy.? is not JSON serializable"):
            await client.get("/return_unserializable_json/")

    async def test_return_schema(self, client):
        response = await client.get("/return-schema/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"name": "Canna"}

    async def test_return_schema_many(self, client):
        response = await client.get("/return-schema-many/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json() == [{"name": "Canna"}, {"name": "Sandy"}]

    async def test_return_schema_empty(self, client):
        response = await client.get("/return-schema-empty/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.content == b""
