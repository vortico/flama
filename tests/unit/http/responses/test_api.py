import json

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields

from flama import exceptions
from flama.http.responses.api import APIErrorResponse, APIResponse


class TestCaseAPIResponse:
    @pytest.fixture(scope="function")
    def schema(self, app):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model("Puppy", name=(str, ...))
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(title="Puppy", fields={"name": typesystem.fields.String()})
        elif app.schema.schema_library.name == "marshmallow":
            schema = type("Puppy", (marshmallow.Schema,), {"name": marshmallow.fields.String(required=True)})
        else:
            raise ValueError(f"Wrong schema lib: {app.schema.schema_library.name}")

        return schema

    def test_init(self, schema):
        response = APIResponse({"name": "Canna"}, schema=schema)

        assert response.schema == schema

    @pytest.mark.parametrize(
        ["use_schema", "content", "expected", "exception"],
        (
            pytest.param(True, {"name": "Canna"}, '{"name":"Canna"}', None, id="schema_and_content"),
            pytest.param(False, {}, "{}", None, id="no_content"),
            pytest.param(False, {"name": "Canna"}, '{"name":"Canna"}', None, id="no_schema"),
            pytest.param(True, {"foo": "bar"}, "", exceptions.SerializationError, id="error"),
        ),
        indirect=["exception"],
    )
    def test_render(self, schema, use_schema, content, expected, exception):
        with exception:
            response = APIResponse(content, schema=schema if use_schema else None)
            assert response.body.decode() == expected


class TestCaseAPIErrorResponse:
    def test_init(self):
        detail = "foo"
        exception = ValueError()
        status_code = 401
        expected_result = {"detail": "foo", "error": "ValueError", "status_code": 401}

        response = APIErrorResponse(detail=detail, status_code=status_code, exception=exception)

        assert response.detail == detail
        assert response.exception == exception
        assert response.status_code == status_code
        assert json.loads(response.body.decode()) == expected_result
