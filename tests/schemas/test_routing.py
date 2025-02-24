import typing as t

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields

import flama.types.websockets
from flama import Component, endpoints, routing, schemas, websockets
from flama.schemas.data_structures import Parameter, ParameterLocation


class Custom: ...


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

        if schemas.lib == pydantic:
            schema = pydantic.create_model("FooSchema", x=(int, ...), y=(str, ...))
        elif schemas.lib == typesystem:
            schema = typesystem.Schema(
                title="FooSchema", fields={"x": typesystem.fields.Integer(), "y": typesystem.fields.String()}
            )
        elif schemas.lib == marshmallow:
            schema = type(
                "FooSchema",
                (marshmallow.Schema,),
                {"x": marshmallow.fields.Integer(), "y": marshmallow.fields.String()},
            )
        else:
            raise ValueError("Wrong schema lib")

        return schema

    @pytest.fixture
    def route(self, request, foo_schema):
        if request.param == "http_function":

            def foo(
                w: int,
                a: Custom,
                z: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema)],
                x: int = 1,
                y: t.Optional[str] = None,
            ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema)]: ...

            return routing.Route("/foo/{w:int}/", endpoint=foo, methods=["GET"])

        elif request.param == "http_endpoint":

            class FooEndpoint(endpoints.HTTPEndpoint):
                def get(
                    self,
                    w: int,
                    a: Custom,
                    z: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema)],
                    x: int = 1,
                    y: t.Optional[str] = None,
                ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema)]: ...

            return routing.Route("/bar/{w:int}/", endpoint=FooEndpoint, methods=["GET"])

        elif request.param == "websocket_function":

            def bar(
                websocket: websockets.WebSocket,
                data: flama.types.websockets.Data,
                w: int,
                a: Custom,
                z: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema)],
                x: int = 1,
                y: t.Optional[str] = None,
            ) -> None: ...

            return routing.WebSocketRoute("/foo/{w:int}/", endpoint=bar)

        elif request.param == "websocket_endpoint":

            class FooWebsocket(endpoints.WebSocketEndpoint):
                async def on_receive(
                    self,
                    websocket: websockets.WebSocket,
                    data: flama.types.websockets.Data,
                    w: int,
                    a: Custom,
                    z: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema)],
                    x: int = 1,
                    y: t.Optional[str] = None,
                ) -> None: ...

            return routing.WebSocketRoute("/foo/{w:int}/", endpoint=FooWebsocket)
        else:
            raise ValueError("Wrong value")

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
                        "x": {
                            "name": "x",
                            "location": ParameterLocation.query,
                            "type": int,
                            "required": False,
                            "default": 1,
                        },
                        "y": {
                            "name": "y",
                            "location": ParameterLocation.query,
                            "type": t.Optional[str],
                            "required": False,
                            "default": None,
                        },
                        "ax": {"name": "ax", "location": ParameterLocation.query, "type": int, "required": True},
                    },
                    "HEAD": {
                        "x": {
                            "name": "x",
                            "location": ParameterLocation.query,
                            "type": int,
                            "required": False,
                            "default": 1,
                        },
                        "y": {
                            "name": "y",
                            "location": ParameterLocation.query,
                            "type": t.Optional[str],
                            "required": False,
                            "default": None,
                        },
                        "ax": {"name": "ax", "location": ParameterLocation.query, "type": int, "required": True},
                    },
                },
                id="http_function",
            ),
            pytest.param(
                "http_endpoint",
                {
                    "GET": {
                        "x": {
                            "name": "x",
                            "location": ParameterLocation.query,
                            "type": int,
                            "required": False,
                            "default": 1,
                        },
                        "y": {
                            "name": "y",
                            "location": ParameterLocation.query,
                            "type": t.Optional[str],
                            "required": False,
                            "default": None,
                        },
                        "ax": {"name": "ax", "location": ParameterLocation.query, "type": int, "required": True},
                    },
                    "HEAD": {
                        "x": {
                            "name": "x",
                            "location": ParameterLocation.query,
                            "type": int,
                            "required": False,
                            "default": 1,
                        },
                        "y": {
                            "name": "y",
                            "location": ParameterLocation.query,
                            "type": t.Optional[str],
                            "required": False,
                            "default": None,
                        },
                        "ax": {"name": "ax", "location": ParameterLocation.query, "type": int, "required": True},
                    },
                },
                id="http_endpoint",
            ),
            pytest.param(
                "websocket_function",
                {
                    "WEBSOCKET": {
                        "x": {
                            "name": "x",
                            "location": ParameterLocation.query,
                            "type": int,
                            "required": False,
                            "default": 1,
                        },
                        "y": {
                            "name": "y",
                            "location": ParameterLocation.query,
                            "type": t.Optional[str],
                            "required": False,
                            "default": None,
                        },
                        "ax": {"name": "ax", "location": ParameterLocation.query, "type": int, "required": True},
                    }
                },
                id="websocket_function",
            ),
            pytest.param(
                "websocket_endpoint",
                {
                    "WEBSOCKET_CONNECT": {},
                    "WEBSOCKET_RECEIVE": {
                        "x": {
                            "name": "x",
                            "location": ParameterLocation.query,
                            "type": int,
                            "required": False,
                            "default": 1,
                        },
                        "y": {
                            "name": "y",
                            "location": ParameterLocation.query,
                            "type": t.Optional[str],
                            "required": False,
                            "default": None,
                        },
                        "ax": {"name": "ax", "location": ParameterLocation.query, "type": int, "required": True},
                    },
                    "WEBSOCKET_DISCONNECT": {},
                },
                id="websocket_endpoint",
            ),
        ),
        indirect=["route"],
    )
    def test_query(self, route, expected_params):
        assert route.parameters.query == {
            method: {k: Parameter(**param) for k, param in params.items()} for method, params in expected_params.items()
        }

    @pytest.mark.parametrize(
        ["route", "expected_params"],
        (
            pytest.param(
                "http_function",
                {
                    "GET": {
                        "w": {"name": "w", "location": ParameterLocation.path, "type": int, "required": True},
                    },
                    "HEAD": {
                        "w": {"name": "w", "location": ParameterLocation.path, "type": int, "required": True},
                    },
                },
                id="http_function",
            ),
            pytest.param(
                "http_endpoint",
                {
                    "GET": {
                        "w": {"name": "w", "location": ParameterLocation.path, "type": int, "required": True},
                    },
                    "HEAD": {
                        "w": {"name": "w", "location": ParameterLocation.path, "type": int, "required": True},
                    },
                },
                id="http_endpoint",
            ),
            pytest.param(
                "websocket_function",
                {
                    "WEBSOCKET": {
                        "w": {"name": "w", "location": ParameterLocation.path, "type": int, "required": True},
                    }
                },
                id="websocket_function",
            ),
            pytest.param(
                "websocket_endpoint",
                {
                    "WEBSOCKET_CONNECT": {},
                    "WEBSOCKET_RECEIVE": {
                        "w": {"name": "w", "location": ParameterLocation.path, "type": int, "required": True},
                    },
                    "WEBSOCKET_DISCONNECT": {},
                },
                id="websocket_endpoint",
            ),
        ),
        indirect=["route"],
    )
    def test_path(self, route, expected_params):
        assert route.parameters.path == {
            method: {k: Parameter(**param) for k, param in params.items()} for method, params in expected_params.items()
        }

    @pytest.mark.parametrize(
        ["route", "expected_params"],
        (
            pytest.param(
                "http_function",
                {
                    "GET": {"name": "z", "location": ParameterLocation.body, "type": None},
                    "HEAD": {"name": "z", "location": ParameterLocation.body, "type": None},
                },
                id="http_function",
            ),
            pytest.param(
                "http_endpoint",
                {
                    "GET": {"name": "z", "location": ParameterLocation.body, "type": None},
                    "HEAD": {"name": "z", "location": ParameterLocation.body, "type": None},
                },
                id="http_endpoint",
            ),
            pytest.param(
                "websocket_function",
                {
                    "WEBSOCKET": {"name": "z", "location": ParameterLocation.body, "type": None},
                },
                id="websocket_function",
            ),
            pytest.param(
                "websocket_endpoint",
                {
                    "WEBSOCKET_CONNECT": None,
                    "WEBSOCKET_RECEIVE": {"name": "z", "location": ParameterLocation.body, "type": None},
                    "WEBSOCKET_DISCONNECT": None,
                },
                id="websocket_endpoint",
            ),
        ),
        indirect=["route"],
    )
    def test_body(self, route, expected_params, foo_schema):
        expected_params = {
            k: Parameter(**{**param, "type": t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema)]})
            if param
            else None
            for k, param in expected_params.items()
        }
        assert route.parameters.body == expected_params

    @pytest.mark.parametrize(
        ["route", "expected_params"],
        (
            pytest.param(
                "http_function",
                {
                    "GET": {"name": "_return", "location": ParameterLocation.response, "type": True},
                    "HEAD": {"name": "_return", "location": ParameterLocation.response, "type": True},
                },
                id="http_function",
            ),
            pytest.param(
                "http_endpoint",
                {
                    "GET": {"name": "_return", "location": ParameterLocation.response, "type": True},
                    "HEAD": {"name": "_return", "location": ParameterLocation.response, "type": True},
                },
                id="http_endpoint",
            ),
            pytest.param(
                "websocket_function",
                {
                    "WEBSOCKET": {"name": "_return", "location": ParameterLocation.response, "type": None},
                },
                id="websocket_function",
            ),
            pytest.param(
                "websocket_endpoint",
                {
                    "WEBSOCKET_CONNECT": {"name": "_return", "location": ParameterLocation.response, "type": None},
                    "WEBSOCKET_RECEIVE": {"name": "_return", "location": ParameterLocation.response, "type": None},
                    "WEBSOCKET_DISCONNECT": {"name": "_return", "location": ParameterLocation.response, "type": None},
                },
                id="websocket_endpoint",
            ),
        ),
        indirect=["route"],
    )
    def test_response(self, route, expected_params, foo_schema):
        expected_params = {
            k: Parameter(
                **{
                    **param,
                    "type": t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema)]
                    if param["type"]
                    else None,
                }
            )
            for k, param in expected_params.items()
        }
        assert route.parameters.response == expected_params
