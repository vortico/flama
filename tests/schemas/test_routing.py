import inspect

import marshmallow
import pytest
import typesystem

from flama import Component, Flama, HTTPEndpoint, Route, Router, WebSocketEndpoint, WebSocketRoute, websockets
from flama.schemas.types import Parameter, ParameterLocation


class Custom:
    ...


class TestCaseRouteFieldsMixin:
    @pytest.fixture
    def component(self):
        class CustomComponent(Component):
            def resolve(self, ax: int) -> Custom:
                return Custom()

        return CustomComponent

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
    def router(self, app):
        return Router(main_app=app)

    @pytest.fixture
    def route(self, foo_schema):
        def foo(w: int, a: Custom, z: foo_schema, x: int = 1, y: str = None) -> foo_schema:
            ...

        return Route("/foo/{w:int}/", endpoint=foo, methods=["GET"])

    @pytest.fixture()
    def endpoint(self, foo_schema):
        class BarEndpoint(HTTPEndpoint):
            def get(self, w: int, a: Custom, z: foo_schema, x: int = 1, y: str = None) -> foo_schema:
                ...

        return Route("/bar/{w:int}/", endpoint=BarEndpoint, methods=["GET"])

    @pytest.fixture()
    def websocket(self, foo_schema):
        class FooWebsocket(WebSocketEndpoint):
            def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data) -> None:
                ...

        return WebSocketRoute("/foo", endpoint=FooWebsocket)

    @pytest.fixture(autouse=True)
    def app(self, app, component, route, endpoint, websocket):
        return Flama(routes=[route, endpoint, websocket], components=[component()], schema=None, docs=None)

    def test_inspect_parameters_from_handler(self, route, app, foo_schema):
        expected_parameters = {
            "x": inspect.Parameter("x", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int, default=1),
            "y": inspect.Parameter("y", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str, default=None),
            "z": inspect.Parameter("z", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=foo_schema),
            "ax": inspect.Parameter("ax", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
            "w": inspect.Parameter("w", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
        }
        assert route.parameters._inspect_parameters_from_handler(route.endpoint, app.components) == expected_parameters

    def test_get_parameters_from_handler(self, route, app, foo_schema):
        expected_query_fields = {
            "x": Parameter("x", ParameterLocation.query, schema_type=int, required=False, default=1),
            "y": Parameter("y", ParameterLocation.query, schema_type=str, required=False, default=None),
            "ax": Parameter("ax", ParameterLocation.query, schema_type=int, required=True),
        }
        expected_path_fields = {
            "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
        }
        expected_body_field = Parameter("z", ParameterLocation.body, schema_type=foo_schema, required=False)
        expected_output_field = Parameter("_output", ParameterLocation.output, schema_type=foo_schema, required=False)

        query_fields, path_fields, body_field, output_field = route.parameters._get_parameters_from_handler(
            route.endpoint, route.param_convertors.keys(), app.components
        )

        assert query_fields == expected_query_fields
        assert path_fields == expected_path_fields
        assert body_field == expected_body_field
        assert output_field == expected_output_field

    def test_get_parameters_function(self, route, app, foo_schema):
        expected_query_fields = {
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
        }
        expected_path_fields = {
            "GET": {
                "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
            },
            "HEAD": {
                "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
            },
        }
        expected_body_field = {
            "GET": Parameter("z", ParameterLocation.body, schema_type=foo_schema, required=False),
            "HEAD": Parameter("z", ParameterLocation.body, schema_type=foo_schema, required=False),
        }
        expected_output_field = {
            "GET": Parameter("_output", ParameterLocation.output, schema_type=foo_schema, required=False),
            "HEAD": Parameter("_output", ParameterLocation.output, schema_type=foo_schema, required=False),
        }

        query_fields, path_fields, body_field, output_field = route.parameters._get_parameters(route)

        assert query_fields == expected_query_fields
        assert path_fields == expected_path_fields
        assert body_field == expected_body_field
        assert output_field == expected_output_field

    def test_get_parameters_endpoint(self, endpoint, app, foo_schema):
        expected_query_fields = {
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
        }
        expected_path_fields = {
            "GET": {
                "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
            },
            "HEAD": {
                "w": Parameter("w", ParameterLocation.path, schema_type=int, required=True),
            },
        }
        expected_body_field = {
            "GET": Parameter("z", ParameterLocation.body, schema_type=foo_schema, required=False),
            "HEAD": Parameter("z", ParameterLocation.body, schema_type=foo_schema, required=False),
        }
        expected_output_field = {
            "GET": Parameter("_output", ParameterLocation.output, schema_type=foo_schema, required=False),
            "HEAD": Parameter("_output", ParameterLocation.output, schema_type=foo_schema, required=False),
        }

        query_fields, path_fields, body_field, output_field = endpoint.parameters._get_parameters(endpoint)

        assert query_fields == expected_query_fields
        assert path_fields == expected_path_fields
        assert body_field == expected_body_field
        assert output_field == expected_output_field

    def test_get_parameters_websocket(self, websocket, app, foo_schema):
        expected_query_fields = {"GET": {}}
        expected_path_fields = {"GET": {}}
        expected_body_field = {"GET": None}
        expected_output_field = {
            "GET": Parameter("_output", ParameterLocation.output, schema_type=None, required=False)
        }

        query_fields, path_fields, body_field, output_field = websocket.parameters._get_parameters(websocket)

        assert query_fields == expected_query_fields
        assert path_fields == expected_path_fields
        assert body_field == expected_body_field
        assert output_field == expected_output_field
