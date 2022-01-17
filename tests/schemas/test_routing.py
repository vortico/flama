import inspect

import pytest
import typesystem

from flama import HTTPEndpoint, Route, Router
from flama.schemas.types import Field, FieldLocation


class TestCaseRouteFieldsMixin:
    @pytest.fixture(scope="class")
    def foo_schema(self):
        return typesystem.Schema({"x": typesystem.fields.Integer(), "y": typesystem.fields.String()})

    @pytest.fixture()
    def router(self):
        return Router()

    @pytest.fixture()
    def route(self, router, foo_schema):
        def foo(w: int, z: foo_schema, x: int = 1, y: str = None) -> foo_schema:
            ...

        return Route("/foo/{w:int}/", endpoint=foo, methods=["GET"], router=router)

    @pytest.fixture()
    def endpoint(self, router, foo_schema):
        class BarEndpoint(HTTPEndpoint):
            def get(self, w: int, z: foo_schema, x: int = 1, y: str = None) -> foo_schema:
                ...

        return Route("/bar/{w:int}/", endpoint=BarEndpoint, methods=["GET"], router=router)

    def test_get_parameters_from_handler(self, route, router, foo_schema):
        expected_parameters = {
            "x": inspect.Parameter("x", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int, default=1),
            "y": inspect.Parameter("y", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str, default=None),
            "z": inspect.Parameter("z", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=foo_schema),
            "w": inspect.Parameter("w", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
        }
        assert route._get_parameters_from_handler(route.endpoint, router) == expected_parameters

    def test_get_fields_from_handler(self, route, router, foo_schema):
        expected_query_fields = {
            "x": Field("x", FieldLocation.query, schema_type=int, required=False, default=1),
            "y": Field("y", FieldLocation.query, schema_type=str, required=False, default=None),
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
            },
            "HEAD": {
                "x": Field("x", FieldLocation.query, schema_type=int, required=False, default=1),
                "y": Field("y", FieldLocation.query, schema_type=str, required=False, default=None),
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
            },
            "HEAD": {
                "x": Field("x", FieldLocation.query, schema_type=int, required=False, default=1),
                "y": Field("y", FieldLocation.query, schema_type=str, required=False, default=None),
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
