import inspect

import marshmallow
import pytest
import typesystem

from flama import Component, Flama, HTTPEndpoint, Route, Router, WebSocketEndpoint, WebSocketRoute, websockets
from flama.schemas.types import Field, FieldLocation


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
    def app(self, app, component):
        return Flama(components=[component()], schema=None, docs=None)

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

    def test_get_parameters_from_handler(self, route, router, foo_schema):
        expected_parameters = {
            "x": inspect.Parameter("x", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int, default=1),
            "y": inspect.Parameter("y", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str, default=None),
            "z": inspect.Parameter("z", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=foo_schema),
            "ax": inspect.Parameter("ax", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
            "w": inspect.Parameter("w", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
        }
        assert route._get_parameters_from_handler(route.endpoint, router) == expected_parameters

    def test_get_fields_from_handler(self, route, router, foo_schema):
        expected_query_fields = {
            "x": Field("x", FieldLocation.query, schema_type=int, required=False, default=1),
            "y": Field("y", FieldLocation.query, schema_type=str, required=False, default=None),
            "ax": Field("ax", FieldLocation.query, schema_type=int, required=True),
        }
        expected_path_fields = {
            "w": Field("w", FieldLocation.path, schema_type=int, required=True),
        }
        expected_body_field = Field("z", FieldLocation.body, schema_type=foo_schema, required=False)
        expected_output_field = Field("_output", FieldLocation.output, schema_type=foo_schema, required=False)

        query_fields, path_fields, body_field, output_field = route._get_fields_from_handler(route.endpoint, router)

        assert query_fields == expected_query_fields
        assert path_fields == expected_path_fields
        assert body_field == expected_body_field
        assert output_field == expected_output_field

    def test_get_fields_function(self, route, router, foo_schema):
        expected_query_fields = {
            "GET": {
                "x": Field("x", FieldLocation.query, schema_type=int, required=False, default=1),
                "y": Field("y", FieldLocation.query, schema_type=str, required=False, default=None),
                "ax": Field("ax", FieldLocation.query, schema_type=int, required=True),
            },
            "HEAD": {
                "x": Field("x", FieldLocation.query, schema_type=int, required=False, default=1),
                "y": Field("y", FieldLocation.query, schema_type=str, required=False, default=None),
                "ax": Field("ax", FieldLocation.query, schema_type=int, required=True),
            },
        }
        expected_path_fields = {
            "GET": {
                "w": Field("w", FieldLocation.path, schema_type=int, required=True),
            },
            "HEAD": {
                "w": Field("w", FieldLocation.path, schema_type=int, required=True),
            },
        }
        expected_body_field = {
            "GET": Field("z", FieldLocation.body, schema_type=foo_schema, required=False),
            "HEAD": Field("z", FieldLocation.body, schema_type=foo_schema, required=False),
        }
        expected_output_field = {
            "GET": Field("_output", FieldLocation.output, schema_type=foo_schema, required=False),
            "HEAD": Field("_output", FieldLocation.output, schema_type=foo_schema, required=False),
        }

        query_fields, path_fields, body_field, output_field = route._get_fields(router)

        assert query_fields == expected_query_fields
        assert path_fields == expected_path_fields
        assert body_field == expected_body_field
        assert output_field == expected_output_field

    def test_get_fields_endpoint(self, endpoint, router, foo_schema):
        expected_query_fields = {
            "GET": {
                "x": Field("x", FieldLocation.query, schema_type=int, required=False, default=1),
                "y": Field("y", FieldLocation.query, schema_type=str, required=False, default=None),
                "ax": Field("ax", FieldLocation.query, schema_type=int, required=True),
            },
            "HEAD": {
                "x": Field("x", FieldLocation.query, schema_type=int, required=False, default=1),
                "y": Field("y", FieldLocation.query, schema_type=str, required=False, default=None),
                "ax": Field("ax", FieldLocation.query, schema_type=int, required=True),
            },
        }
        expected_path_fields = {
            "GET": {
                "w": Field("w", FieldLocation.path, schema_type=int, required=True),
            },
            "HEAD": {
                "w": Field("w", FieldLocation.path, schema_type=int, required=True),
            },
        }
        expected_body_field = {
            "GET": Field("z", FieldLocation.body, schema_type=foo_schema, required=False),
            "HEAD": Field("z", FieldLocation.body, schema_type=foo_schema, required=False),
        }
        expected_output_field = {
            "GET": Field("_output", FieldLocation.output, schema_type=foo_schema, required=False),
            "HEAD": Field("_output", FieldLocation.output, schema_type=foo_schema, required=False),
        }

        query_fields, path_fields, body_field, output_field = endpoint._get_fields(router)

        assert query_fields == expected_query_fields
        assert path_fields == expected_path_fields
        assert body_field == expected_body_field
        assert output_field == expected_output_field

    def test_get_fields_websocket(self, websocket, router, foo_schema):
        expected_query_fields = {"GET": {}}
        expected_path_fields = {"GET": {}}
        expected_body_field = {"GET": None}
        expected_output_field = {"GET": Field("_output", FieldLocation.output, schema_type=None, required=False)}

        query_fields, path_fields, body_field, output_field = websocket._get_fields(router)

        assert query_fields == expected_query_fields
        assert path_fields == expected_path_fields
        assert body_field == expected_body_field
        assert output_field == expected_output_field
