import pytest
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from starlette_api.applications import Starlette
from starlette_api.components import Component
from starlette_api.endpoints import HTTPEndpoint


class Puppy:
    name = "Canna"


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


app = Starlette(components=[PuppyComponent()])


@app.route("/http-view")
async def puppy_http_view(puppy: Puppy):
    return JSONResponse({"puppy": puppy.name})


@app.route("/http-endpoint")
class PuppyHTTPEndpoint(HTTPEndpoint):
    async def get(self, puppy: Puppy):
        return JSONResponse({"puppy": puppy.name})


@app.websocket_route("/websocket-view")
async def puppy_websocket_view(session: WebSocket, puppy: Puppy):
    await session.accept()
    await session.send_json({"puppy": puppy.name})
    await session.close()


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
