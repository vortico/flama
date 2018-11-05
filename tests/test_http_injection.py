import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from starlette_api import http
from starlette_api.applications import Starlette
from starlette_api.endpoints import HTTPEndpoint

app = Starlette()


@app.route("/http-view")
async def http_view(request: Request, path: http.Path):
    return JSONResponse({"path": path, "headers": dict(request.headers)})


@app.route("/http-endpoint")
class PuppyHTTPEndpoint(HTTPEndpoint):
    async def get(self, request: Request, path: http.Path):
        return JSONResponse({"path": path, "headers": dict(request.headers)})


@app.websocket_route("/websocket-view")
async def websocket_view(session: WebSocket, path: http.Path):
    await session.accept()
    await session.send_json({"path": path, "headers": dict(session.headers)})
    await session.close()


@pytest.fixture
def client():
    return TestClient(app)


class TestCaseHttpInjection:
    def test_injection_http_view(self, client):
        response = client.get("/http-view")
        assert response.status_code == 200
        body = response.json()
        assert body["path"] == "/http-view"

    def test_injection_http_endpoint(self, client):
        response = client.get("/http-endpoint")
        assert response.status_code == 200
        body = response.json()
        assert body["path"] == "/http-endpoint"

    def test_injection_websocket_view(self, client):
        with client.websocket_connect("/websocket-view") as websocket:
            assert websocket.receive_json()["path"] == "/websocket-view"
