import typing as t
import warnings
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import marshmallow
import pydantic
import pytest
import starlette.websockets
import typesystem
import typesystem.fields

from flama import Component, Flama, exceptions, schemas, types, websockets
from flama.endpoints import HTTPEndpoint, WebSocketEndpoint


class Puppy:
    name = "Canna"


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


@pytest.fixture(scope="module")
def app(app):
    return Flama(schema=None, docs=None, components=[PuppyComponent()])


class TestCaseHTTPEndpoint:
    @pytest.fixture
    def endpoint(self, app, asgi_scope, asgi_receive, asgi_send):
        @app.route("/")
        class FooEndpoint(HTTPEndpoint):
            def get(self):
                ...

        asgi_scope["app"] = app
        asgi_scope["root_app"] = app
        asgi_scope["type"] = "http"
        return FooEndpoint(asgi_scope, asgi_receive, asgi_send)

    @pytest.fixture(scope="class")
    def puppy_schema(self, app):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model("Puppy", name=(str, ...))
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(title="Puppy", fields={"name": typesystem.fields.String()})
        elif app.schema.schema_library.lib == marshmallow:
            schema = type("Puppy", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
        else:
            raise ValueError("Wrong schema lib")

        return schema

    @pytest.fixture(scope="class")
    def puppy_endpoint(self, app, puppy_schema):
        @app.route("/puppy/")
        class PuppyEndpoint(HTTPEndpoint):
            def get(self, puppy: Puppy) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(puppy_schema)]:
                return {"name": puppy.name}

            async def post(
                self, puppy: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(puppy_schema)]
            ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(puppy_schema)]:
                return puppy

        return PuppyEndpoint

    @pytest.mark.parametrize(
        ["method", "params", "status_code", "expected_response"],
        (
            pytest.param("get", {}, 200, {"name": "Canna"}, id="get"),
            pytest.param("post", {"json": {"name": "Canna"}}, 200, {"name": "Canna"}, id="post"),
            pytest.param(
                "patch",
                {},
                405,
                {"detail": "Method Not Allowed", "error": "HTTPException", "status_code": 405},
                id="method_not_allowed",
            ),
        ),
    )
    async def test_request(self, app, client, puppy_endpoint, method, params, status_code, expected_response):
        response = await client.request(method, "/puppy/", **params)

        assert response.status_code == status_code
        assert response.json() == expected_response

    def test_init(self, app, asgi_scope, asgi_receive, asgi_send):
        with patch("flama.endpoints.http.Request") as request_mock:

            class FooEndpoint(HTTPEndpoint):
                def get(self):
                    ...

            route = app.add_route("/", FooEndpoint)
            asgi_scope = types.Scope(
                {
                    **asgi_scope,
                    "app": app,
                    "root_app": app,
                    "type": "http",
                    "method": "GET",
                    "path": "/",
                    "path_params": {},
                    "endpoint": FooEndpoint,
                    "route": route,
                }
            )
            endpoint = HTTPEndpoint(asgi_scope, asgi_receive, asgi_send)
            assert endpoint.state == {
                "scope": asgi_scope,
                "receive": asgi_receive,
                "send": asgi_send,
                "exc": None,
                "app": app,
                "root_app": app,
                "path_params": {},
                "route": route,
                "request": request_mock(),
            }

    def test_await(self, endpoint):
        with patch.object(endpoint, "dispatch"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                endpoint.__await__()

            assert endpoint.dispatch.call_args_list == [call()]

    def test_allowed_methods(self, endpoint):
        assert endpoint.allowed_methods() == {"GET", "HEAD"}

        class BarEndpoint(HTTPEndpoint):
            def post(self):
                ...

        assert BarEndpoint.allowed_methods() == {"POST"}

    def test_handler(self, endpoint):
        endpoint.state["request"].scope["method"] = "GET"
        assert endpoint.handler == endpoint.get

    async def test_dispatch(self, app, endpoint):
        injected_mock = MagicMock()
        app.injector.inject = AsyncMock(return_value=injected_mock)
        with patch("flama.endpoints.concurrency.run") as run_mock:
            await endpoint.dispatch()

            assert app.injector.inject.call_args_list == [call(endpoint.get, endpoint.state)]
            assert run_mock.call_args_list == [call(injected_mock)]


class TestCaseWebSocketEndpoint:
    @pytest.fixture
    def endpoint(self, app, asgi_scope, asgi_receive, asgi_send):
        @app.websocket_route("/")
        class FooEndpoint(WebSocketEndpoint):
            def get(self):
                ...

        asgi_scope["app"] = app
        asgi_scope["root_app"] = app
        asgi_scope["type"] = "websocket"
        with patch("flama.endpoints.websockets.WebSocket", spec=websockets.WebSocket):
            return FooEndpoint(asgi_scope, asgi_receive, asgi_send)

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    @pytest.mark.parametrize(
        ["encoding", "send_method", "data", "expected_result"],
        (
            pytest.param("bytes", "send_bytes", b"foo", {"bytes": b"foo", "type": "websocket.send"}, id="bytes"),
            pytest.param(
                "bytes", "send_text", "foo", {"code": 1003, "type": "websocket.close", "reason": ""}, id="bytes_wrong"
            ),
            pytest.param("text", "send_text", "foo", {"text": "foo", "type": "websocket.send"}, id="text"),
            pytest.param(
                "text", "send_bytes", b"foo", {"code": 1003, "type": "websocket.close", "reason": ""}, id="text_wrong"
            ),
            pytest.param(
                "json", "send_json", {"foo": "bar"}, {"text": '{"foo":"bar"}', "type": "websocket.send"}, id="json"
            ),
            pytest.param(
                "json",
                "send_bytes",
                b'{"foo": "bar"}',
                {"text": '{"foo":"bar"}', "type": "websocket.send"},
                id="json_using_bytes",
            ),
            pytest.param(
                "json",
                "send_text",
                b'{"foo":"bar"}',
                {"text": '{"foo":"bar"}', "type": "websocket.send"},
                id="json_using_text",
            ),
            pytest.param(
                "json", "send_bytes", b"foo", {"code": 1003, "type": "websocket.close", "reason": ""}, id="json_wrong"
            ),
            pytest.param(
                None,
                "send_bytes",
                b"foo",
                {"bytes": b"foo", "type": "websocket.send"},
                id="default_encoding",
            ),
            pytest.param(
                "unknown",
                "send_bytes",
                b"foo",
                {"code": 1003, "type": "websocket.close", "reason": ""},
                id="unknown_encoding",
            ),
        ),
    )
    def test_receive(self, app, client, encoding, send_method, data, expected_result):
        encoding_ = encoding

        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = encoding_

            async def on_receive(self, websocket: websockets.WebSocket, data: types.Data):
                await getattr(websocket, f"send_{encoding_ or 'bytes'}")(data)

        with client.websocket_connect("/") as ws:
            getattr(ws, send_method)(data)
            result = ws.receive()

        assert result == expected_result

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    def test_injecting_component(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            encoding = types.Encoding("bytes")

            async def on_connect(self, websocket: websockets.WebSocket):
                await websocket.accept()

            async def on_receive(self, websocket: websockets.WebSocket, data: types.Data, puppy: Puppy):
                await websocket.send_json({"puppy": puppy.name})

            async def on_disconnect(self, websocket: websockets.WebSocket, websocket_code: types.Code):
                pass

        with client.websocket_connect("/") as ws:
            ws.send_bytes(b"")
            result = ws.receive_json()

        assert result == {"puppy": "Canna"}

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    def test_fail_connecting(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            async def on_connect(self, websocket: websockets.WebSocket):
                raise Exception("Error connecting socket")

        with pytest.raises(Exception, match="Error connecting socket"), client.websocket_connect("/") as ws:
            ws.send_bytes("foo")

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    def test_fail_receiving(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(WebSocketEndpoint):
            async def on_receive(self, websocket: websockets.WebSocket, data: types.Data):
                raise ValueError("Foo")

        with pytest.raises(ValueError, match="Foo"), client.websocket_connect("/") as ws:
            ws.send_bytes("foo")
            result = ws.receive()

            assert result == {"code": 1011, "type": "websocket.close", "reason": ""}

    def test_init(self, app, asgi_scope, asgi_receive, asgi_send):
        with patch("flama.endpoints.websockets.WebSocket") as websocket_mock:
            route = app.add_websocket_route("/", WebSocketEndpoint)
            asgi_scope = types.Scope(
                {
                    **asgi_scope,
                    "app": app,
                    "root_app": app,
                    "type": "websocket",
                    "path": "/",
                    "path_params": {},
                    "endpoint": WebSocketEndpoint,
                    "route": route,
                }
            )
            endpoint = WebSocketEndpoint(asgi_scope, asgi_receive, asgi_send)
            assert endpoint.state == {
                "scope": asgi_scope,
                "receive": asgi_receive,
                "send": asgi_send,
                "exc": None,
                "app": app,
                "root_app": app,
                "path_params": {},
                "route": route,
                "websocket": websocket_mock(),
                "websocket_code": None,
                "websocket_encoding": None,
                "websocket_message": None,
            }

    def test_await(self, endpoint):
        with patch.object(endpoint, "dispatch"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                endpoint.__await__()

            assert endpoint.dispatch.call_args_list == [call()]

    def test_allowed_handlers(self, endpoint):
        assert endpoint.allowed_handlers() == {
            "WEBSOCKET_CONNECT": endpoint.__class__.on_connect,
            "WEBSOCKET_RECEIVE": endpoint.__class__.on_receive,
            "WEBSOCKET_DISCONNECT": endpoint.__class__.on_disconnect,
        }

    @pytest.mark.parametrize(
        ["endpoint_receive", "websocket_receive", "exception", "result_code", "result_message"],
        (
            pytest.param(
                [None, None, None],
                [
                    {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                    {"type": "websocket.disconnect", "code": 1000},
                ],
                None,
                1000,
                {"type": "websocket.disconnect", "code": 1000},
                id="ok",
            ),
            pytest.param(
                [None, None, None],
                [
                    {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                    starlette.websockets.WebSocketDisconnect(1006, "Abnormal Closure"),
                ],
                exceptions.WebSocketException(1006, "Abnormal Closure"),
                1006,
                {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                id="disconnect",
            ),
            pytest.param(
                [None, exceptions.WebSocketException(1003, "Unsupported Data"), None],
                [{"type": "websocket.receive", "code": 1000, "bytes": "foo"}],
                exceptions.WebSocketException(1003, "Unsupported Data"),
                1003,
                {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                id="websocket_exception",
            ),
            pytest.param(
                [None, ValueError("Foo"), None],
                [{"type": "websocket.receive", "code": 1000, "bytes": "foo"}],
                ValueError("Foo"),
                1011,
                {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                id="exception",
            ),
        ),
        indirect=["exception"],
    )
    async def test_dispatch(
        self, app, endpoint, endpoint_receive, websocket_receive, exception, result_code, result_message
    ):
        app.injector.inject = AsyncMock(side_effect=[AsyncMock(side_effect=x) for x in endpoint_receive])
        endpoint.state["websocket"].receive = AsyncMock(side_effect=websocket_receive)
        type(endpoint.state["websocket"]).is_connected = PropertyMock(side_effect=[True, False])

        with exception:
            await endpoint.dispatch()

        assert endpoint.state["websocket_code"] == result_code
        assert endpoint.state["websocket_message"] == result_message

    async def test_on_connect(self, endpoint):
        websocket = MagicMock(websockets.WebSocket)

        await endpoint.on_connect(websocket)

        assert websocket.accept.call_args_list == [call()]

    async def test_on_receive(self, endpoint):
        websocket = MagicMock(websockets.WebSocket)

        await endpoint.on_receive(websocket, b"foo")

    async def test_on_disconnect(self, endpoint):
        websocket = MagicMock(websockets.WebSocket)

        await endpoint.on_disconnect(websocket, types.Code(1000))

        assert websocket.close.call_args_list == [call(types.Code(1000))]
