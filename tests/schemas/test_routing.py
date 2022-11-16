import marshmallow
import pytest
import typesystem

import flama.types.websockets
from flama import Component, HTTPEndpoint, Route, WebSocketEndpoint, WebSocketRoute, websockets
from flama.schemas.data_structures import Parameter
from flama.schemas.types import ParameterLocation


class Custom:
    ...


class TestCaseRouteFieldsMixin:
    @pytest.fixture
    def component(self):
        class CustomComponent(Component):
            def resolve(self, ax: int) -> Custom:
                return Custom()

        return CustomComponent()

    @pytest.fixture
    def foo_schema(self, app):
        from flama import schemas

        if schemas.lib == typesystem:
            schema = typesystem.Schema({"x": typesystem.fields.Integer(), "y": typesystem.fields.String()})
        elif schemas.lib == marshmallow:
            schema = type(
                "FooSchema",
                (marshmallow.Schema,),
                {"x": marshmallow.fields.Integer(), "y": marshmallow.fields.String()},
            )
        else:
            raise ValueError("Wrong schema lib")

        app.schema.schemas["FooSchema"] = schema
        return schema

    @pytest.fixture
    def route(self, request, foo_schema):
        if request.param == "http_function":

            def foo(w: int, a: Custom, z: foo_schema, x: int = 1, y: str = None) -> foo_schema:
                ...

            return Route("/foo/{w:int}/", endpoint=foo, methods=["GET"])

        if request.param == "http_endpoint":

            class BarEndpoint(HTTPEndpoint):
                def get(self, w: int, a: Custom, z: foo_schema, x: int = 1, y: str = None) -> foo_schema:
                    ...

            return Route("/bar/{w:int}/", endpoint=BarEndpoint, methods=["GET"])

        if request.param == "websocket_function":

            def foo(
                websocket: websockets.WebSocket,
                data: flama.types.websockets.Data,
                w: int,
                a: Custom,
                z: foo_schema,
                x: int = 1,
                y: str = None,
            ) -> None:
                ...

            return WebSocketRoute("/foo/{w:int}/", endpoint=foo)

        if request.param == "websocket_endpoint":

            class FooWebsocket(WebSocketEndpoint):
                def on_receive(
                    self,
                    websocket: websockets.WebSocket,
                    data: flama.types.websockets.Data,
                    w: int,
                    a: Custom,
                    z: foo_schema,
                    x: int = 1,
                    y: str = None,
                ) -> None:
                    ...

            return WebSocketRoute("/foo/{w:int}/", endpoint=FooWebsocket)

    @pytest.fixture(scope="function", autouse=True)
    def add_component(self, app, component):
        app.add_component(component)

    @pytest.mark.parametrize(
        ["route", "expected_params"],
        (
            pytest.param(
                "http_function",
                {
                    "GET": {
                        "x": Parameter("x", ParameterLocation.query, schema_type=int, required=False, default=1),
                        "y": Parameter("y", ParameterLocation.query, schema_type=str, required=False, default=None),
                        "ax": Parameter("ax", ParameterLocation.query, schema_type=int, required=True),
                    },
                    "HEAD": {
                        "x": Parameter("x", ParameterLocation.query, schema_type=int, required=False, default=1),
                        "y": Parameter("y", ParameterLocation.query, schema_type=str, required=False, default=None),
                        "ax": Parameter("ax", ParameterLocation.query, schema_type=int, required=True),
                    },
                },
                id="http_function",
            ),
            pytest.param(
                "http_endpoint",
                {
                    "GET": {
                        "x": Parameter("x", ParameterLocation.query, schema_type=int, required=False, default=1),
                        "y": Parameter("y", ParameterLocation.query, schema_type=str, required=False, default=None),
                        "ax": Parameter("ax", ParameterLocation.query, schema_type=int, required=True),
                    },
                    "HEAD": {
                        "x": Parameter("x", ParameterLocation.query, schema_type=int, required=False, default=1),
                        "y": Parameter("y", ParameterLocation.query, schema_type=str, required=False, default=None),
                        "ax": Parameter("ax", ParameterLocation.query, schema_type=int, required=True),
                    },
                },
                id="http_endpoint",
            ),
            pytest.param(
                "websocket_function",
                {
                    "WEBSOCKET": {
                        "x": Parameter("x", ParameterLocation.query, schema_type=int, required=False, default=1),
                        "y": Parameter("y", ParameterLocation.query, schema_type=str, required=False, default=None),
                        "ax": Parameter("ax", ParameterLocation.query, schema_type=int, required=True),
                    }
                },
                id="websocket_function",
            ),
            pytest.param(
                "websocket_endpoint",
                {
                    "WEBSOCKET_CONNECT": {},
                    "WEBSOCKET_RECEIVE": {
                        "x": Parameter("x", ParameterLocation.query, schema_type=int, required=False, default=1),
                        "y": Parameter("y", ParameterLocation.query, schema_type=str, required=False, default=None),
                        "ax": Parameter("ax", ParameterLocation.query, schema_type=int, required=True),
                    },
                    "WEBSOCKET_DISCONNECT": {},
                },
                id="websocket_endpoint",
            ),
        ),
        indirect=["route"],
    )
    def test_query(self, route, expected_params):
        assert route.parameters.query == expected_params

    @pytest.mark.parametrize(
        ["route", "expected_params"],
        (
            pytest.param(
                "http_function",
                {
                    "GET": {
                        "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
                    },
                    "HEAD": {
                        "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
                    },
                },
                id="http_function",
            ),
            pytest.param(
                "http_endpoint",
                {
                    "GET": {
                        "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
                    },
                    "HEAD": {
                        "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
                    },
                },
                id="http_endpoint",
            ),
            pytest.param(
                "websocket_function",
                {
                    "WEBSOCKET": {
                        "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
                    }
                },
                id="websocket_function",
            ),
            pytest.param(
                "websocket_endpoint",
                {
                    "WEBSOCKET_CONNECT": {},
                    "WEBSOCKET_RECEIVE": {
                        "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
                    },
                    "WEBSOCKET_DISCONNECT": {},
                },
                id="websocket_endpoint",
            ),
        ),
        indirect=["route"],
    )
    def test_path(self, route, expected_params):
        assert route.parameters.path == expected_params

    @pytest.mark.parametrize(
        ["route", "expected_params"],
        (
            pytest.param(
                "http_function",
                {
                    "GET": Parameter("z", ParameterLocation.body, schema_type=None, required=False),
                    "HEAD": Parameter("z", ParameterLocation.body, schema_type=None, required=False),
                },
                id="http_function",
            ),
            pytest.param(
                "http_endpoint",
                {
                    "GET": Parameter("z", ParameterLocation.body, schema_type=None, required=False),
                    "HEAD": Parameter("z", ParameterLocation.body, schema_type=None, required=False),
                },
                id="http_endpoint",
            ),
            pytest.param(
                "websocket_function",
                {
                    "WEBSOCKET": Parameter("z", ParameterLocation.body, schema_type=None, required=False),
                },
                id="websocket_function",
            ),
            pytest.param(
                "websocket_endpoint",
                {
                    "WEBSOCKET_CONNECT": None,
                    "WEBSOCKET_RECEIVE": Parameter("z", ParameterLocation.body, schema_type=None, required=False),
                    "WEBSOCKET_DISCONNECT": None,
                },
                id="websocket_endpoint",
            ),
        ),
        indirect=["route"],
    )
    def test_body(self, route, expected_params, foo_schema):
        expected_params = {
            k: Parameter(v.name, v.location, foo_schema, v.required) if v else None for k, v in expected_params.items()
        }
        assert route.parameters.body == expected_params

    @pytest.mark.parametrize(
        ["route", "expected_params"],
        (
            pytest.param(
                "http_function",
                {
                    "GET": Parameter("_return", ParameterLocation.response, schema_type=True, required=False),
                    "HEAD": Parameter("_return", ParameterLocation.response, schema_type=True, required=False),
                },
                id="http_function",
            ),
            pytest.param(
                "http_endpoint",
                {
                    "GET": Parameter("_return", ParameterLocation.response, schema_type=True, required=False),
                    "HEAD": Parameter("_return", ParameterLocation.response, schema_type=True, required=False),
                },
                id="http_endpoint",
            ),
            pytest.param(
                "websocket_function",
                {
                    "WEBSOCKET": Parameter("_return", ParameterLocation.response, schema_type=None, required=False),
                },
                id="websocket_function",
            ),
            pytest.param(
                "websocket_endpoint",
                {
                    "WEBSOCKET_CONNECT": Parameter(
                        "_return", ParameterLocation.response, schema_type=None, required=False
                    ),
                    "WEBSOCKET_RECEIVE": Parameter(
                        "_return", ParameterLocation.response, schema_type=None, required=False
                    ),
                    "WEBSOCKET_DISCONNECT": Parameter(
                        "_return", ParameterLocation.response, schema_type=None, required=False
                    ),
                },
                id="websocket_endpoint",
            ),
        ),
        indirect=["route"],
    )
    def test_response(self, route, expected_params, foo_schema):
        expected_params = {
            k: Parameter(v.name, v.location, foo_schema if v.schema_type else None, v.required)
            for k, v in expected_params.items()
        }
        assert route.parameters.response == expected_params
