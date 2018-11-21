import pytest
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from starlette_api.applications import Starlette
from starlette_api.components import Component
from starlette_api.endpoints import HTTPEndpoint
from starlette_api.exceptions import ComponentNotFound, ConfigurationError


class Puppy:
    name = "Canna"


class Unknown(Puppy):
    pass


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


class UnhandledComponent(Component):
    def resolve(self):
        pass


app = Starlette(components=[PuppyComponent()])


@app.route("/http-view")
async def puppy_http_view(puppy: Puppy):
    return JSONResponse({"puppy": puppy.name})


@app.route("/http-endpoint", methods=["GET"])
class PuppyHTTPEndpoint(HTTPEndpoint):
    async def get(self, puppy: Puppy):
        return JSONResponse({"puppy": puppy.name})


@app.websocket_route("/websocket-view")
async def puppy_websocket_view(session: WebSocket, puppy: Puppy):
    await session.accept()
    await session.send_json({"puppy": puppy.name})
    await session.close()


@app.route("/unknown")
def unknown_view(unknown: Unknown):
    return JSONResponse({"foo": "bar"})


@pytest.fixture
def client():
    return TestClient(app)


class TestCaseComponentsInjection:
    def test_injection_http_view(self, client):
        response = client.get("/http-view")
        assert response.status_code == 200
        assert response.json() == {"puppy": "Canna"}

    def test_injection_http_endpoint(self, client):
        response = client.get("/http-endpoint")
        assert response.status_code == 200
        assert response.json() == {"puppy": "Canna"}

    def test_injection_websocket_view(self, client):
        with client.websocket_connect("/websocket-view") as websocket:
            assert websocket.receive_json() == {"puppy": "Canna"}

    def test_unknown_component(self, client):
        with pytest.raises(
            ComponentNotFound, match='No component able to handle parameter "unknown" in function "unknown_view"'
        ):
            client.get("/unknown")

    def test_unhandled_component(self):
        app_ = Starlette(components=[UnhandledComponent()])

        @app_.route("/")
        def foo(unknown: Unknown):
            return JSONResponse({"foo": "bar"})

        client = TestClient(app_)

        with pytest.raises(
            ConfigurationError,
            match=r'Component "UnhandledComponent" must include a return annotation on the `resolve\(\)` method, '
            "or override `can_handle_parameter`",
        ):
            client.get("/")
