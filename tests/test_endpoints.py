import marshmallow
import pytest
import typesystem

from flama import Component, exceptions, websockets
from flama.endpoints import HTTPEndpoint, WebSocketEndpoint


class Puppy:
    name = "Canna"


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


@pytest.fixture(scope="class")
def app(app):
    app.router._components.append(PuppyComponent())
    return app


@pytest.fixture(scope="class")
def puppy_schema(app):
    from flama import schemas

    if schemas.lib == typesystem:
        schema = typesystem.Schema(fields={"name": typesystem.fields.String()})
    elif schemas.lib == marshmallow:
        schema = type(
            "Puppy",
            (marshmallow.Schema,),
            {
                "name": marshmallow.fields.String(),
            },
        )
    else:
        raise ValueError("Wrong schema lib")

    app.schema.schemas["Puppy"] = schema
    return schema


class TestCaseHTTPEndpoint:
    def test_custom_component(self, app, client):
        @app.route("/custom-component/", methods=["GET"])
        class PuppyHTTPEndpoint(HTTPEndpoint):
            def get(self, puppy: Puppy):
                return puppy.name

        response = client.get("/custom-component/")

        assert response.status_code == 200
        assert response.json() == "Canna"

    def test_query_param(self, app, client, puppy_schema):
        @app.route("/query-param/", methods=["GET"])
        class QueryParamHTTPEndpoint(HTTPEndpoint):
            async def get(self, param: str) -> puppy_schema:
                return {"name": param}

        response = client.get("/query-param/", params={"param": "Canna"})

        assert response.status_code == 200
        assert response.json() == {"name": "Canna"}

    def test_path_param(self, app, client, puppy_schema):
        @app.route("/path-param/{param}/", methods=["GET"])
        class PathParamHTTPEndpoint(HTTPEndpoint):
            async def get(self, param: str) -> puppy_schema:
                return {"name": param}

        response = client.get("/path-param/Canna/")

        assert response.status_code == 200
        assert response.json() == {"name": "Canna"}

    def test_body_param(self, app, client, puppy_schema):
        @app.route("/body-param/", methods=["POST"])
        class BodyParamHTTPEndpoint(HTTPEndpoint):
            async def post(self, param: puppy_schema) -> puppy_schema:
                return {"name": param["name"]}

        response = client.post("/body-param/", json={"name": "Canna"})

        assert response.status_code == 200
        assert response.json() == {"name": "Canna"}

    def test_not_found(self, app, client):
        response = client.get("/not-found")
        assert response.status_code == 404


class TestCaseWebSocketEndpoint:
    def test_bytes(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "bytes"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                await websocket.send_bytes(data)

        with client.websocket_connect("/") as ws:
            ws.send_bytes(b"foo")
            result = ws.receive_bytes()

        assert result == b"foo"

    def test_bytes_wrong_format(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "bytes"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                if data:
                    await websocket.send_bytes(data)

        with client.websocket_connect("/") as ws:
            ws.send_text("foo")
            result = ws.receive()

        assert result["code"] == 1003
        assert result["type"] == "websocket.close"

    def test_text(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "text"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                await websocket.send_text(data)

        with client.websocket_connect("/") as ws:
            ws.send_text("foo")
            result = ws.receive_text()

        assert result == "foo"

    def test_text_wrong_format(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "text"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                if data:
                    await websocket.send_text(data)

        with client.websocket_connect("/") as ws:
            ws.send_bytes(b"foo")
            result = ws.receive()

        assert result["code"] == 1003
        assert result["type"] == "websocket.close"

    def test_json(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "json"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                await websocket.send_json(data)

        with client.websocket_connect("/") as ws:
            ws.send_json({"foo": "bar"})
            result = ws.receive_json()

        assert result == {"foo": "bar"}

    def test_json_using_bytes(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "json"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                await websocket.send_json(data)

        with client.websocket_connect("/") as ws:
            ws.send_bytes(b'{"foo": "bar"}')
            result = ws.receive_json()

        assert result == {"foo": "bar"}

    def test_json_using_text(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "json"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                await websocket.send_json(data)

        with client.websocket_connect("/") as ws:
            ws.send_text('{"foo": "bar"}')
            result = ws.receive_json()

        assert result == {"foo": "bar"}

    def test_json_wrong_format(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "json"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                if data:
                    await websocket.send_json(data)

        with client.websocket_connect("/") as ws:
            ws.send_text("foo")
            result = ws.receive()

        assert result["code"] == 1003
        assert result["type"] == "websocket.close"

    def test_unknown_encoding(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "unknown"

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                if data:
                    await websocket.send_json(data)

        with client.websocket_connect("/") as ws:
            ws.send_text("foo")
            result = ws.receive()

        assert result["code"] == 1003
        assert result["type"] == "websocket.close"

    def test_default_encoding(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                if data:
                    await websocket.send_bytes(data)

        with client.websocket_connect("/") as ws:
            ws.send_bytes(b"foo")
            result = ws.receive_bytes()

        assert result == b"foo"

    def test_injecting_component(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = "bytes"

            async def on_connect(self, websocket: websockets.WebSocket):
                await websocket.accept()

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data, puppy: Puppy):
                await websocket.send_json({"puppy": puppy.name})

            async def on_disconnect(self, websocket: websockets.WebSocket, websocket_code: websockets.Code):
                pass

        with client.websocket_connect("/") as ws:
            ws.send_bytes(b"")
            result = ws.receive_json()

        assert result == {"puppy": "Canna"}

    def test_fail_connecting(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            async def on_connect(self, websocket: websockets.WebSocket):
                raise Exception

        with pytest.raises(
            exceptions.WebSocketConnectionException, match="Error connecting socket"
        ), client.websocket_connect("/") as ws:
            ws.send_bytes("foo")

    def test_fail_receiving(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                raise Exception

        with pytest.raises(Exception), client.websocket_connect("/") as ws:
            ws.send_bytes("foo")
            result = ws.receive()

        assert result["code"] == 1011
        assert result["type"] == "websocket.close"
