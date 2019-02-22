import marshmallow
import pytest
from starlette.testclient import TestClient

from starlette_api.applications import Starlette
from starlette_api.components import Component
from starlette_api.endpoints import HTTPEndpoint


class Puppy:
    name = "Canna"


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


class BodyParam(marshmallow.Schema):
    name = marshmallow.fields.String()


app = Starlette(components=[PuppyComponent()])


@app.route("/custom-component/", methods=["GET"])
class PuppyHTTPEndpoint(HTTPEndpoint):
    def get(self, puppy: Puppy):
        return puppy.name


@app.route("/query-param/", methods=["GET"])
class QueryParamHTTPEndpoint(HTTPEndpoint):
    async def get(self, param: str) -> BodyParam:
        return {"name": param}


@app.route("/path-param/{param}/", methods=["GET"])
class PathParamHTTPEndpoint(HTTPEndpoint):
    async def get(self, param: str) -> BodyParam:
        return {"name": param}


@app.route("/body-param/", methods=["POST"])
class BodyParamHTTPEndpoint(HTTPEndpoint):
    async def post(self, param: BodyParam) -> BodyParam:
        return {"name": param["name"]}


@pytest.fixture
def client():
    return TestClient(app)


class TestCaseEndpoints:
    def test_custom_component(self, client):
        response = client.get("/custom-component/")
        assert response.status_code == 200
        assert response.content == b"Canna"

    def test_query_param(self, client):
        response = client.get("/query-param/", params={"param": "Canna"})
        assert response.status_code == 200
        assert response.json() == {"name": "Canna"}

    def test_path_param(self, client):
        response = client.get("/path-param/Canna/")
        assert response.status_code == 200
        assert response.json() == {"name": "Canna"}

    def test_body_param(self, client):
        response = client.post("/body-param/", json={"name": "Canna"})
        assert response.status_code == 200
        assert response.json() == {"name": "Canna"}

    def test_not_found(self, client):
        response = client.get("/not-found")
        assert response.status_code == 404
