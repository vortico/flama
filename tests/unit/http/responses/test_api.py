import json

import marshmallow
import pydantic
import pytest

from flama import types
from flama.http import SerializationError
from flama.http.responses.api import APIErrorResponse, APIResponse
from flama.schemas.libs._libraries import libraries


class TestCaseAPIResponse:
    @pytest.fixture(scope="function")
    def schema(self, app):
        if libraries.default.name == "pydantic":
            schema = pydantic.create_model("Puppy", name=(str, ...))
        elif libraries.default.name == "marshmallow":
            schema = type("Puppy", (marshmallow.Schema,), {"name": marshmallow.fields.String(required=True)})
        else:
            raise ValueError(f"Wrong schema lib: {libraries.default.name}")

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
            pytest.param(True, {"foo": "bar"}, "", SerializationError, id="error"),
        ),
        indirect=["exception"],
    )
    def test_render(self, schema, use_schema, content, expected, exception):
        with exception:
            response = APIResponse(content, schema=schema if use_schema else None)
            assert response.body.decode() == expected

    def test_schema_set_after_init(self, schema):
        response = APIResponse({"name": "Canna", "age": 3})

        response.schema = schema

        assert response.body == b'{"name":"Canna"}'


class TestCaseAPIErrorResponse:
    @pytest.mark.parametrize(
        ["kwargs", "expected"],
        (
            pytest.param(
                {"status_code": 404},
                {"type": "about:blank", "title": "Not Found", "status": 404, "detail": "Not Found"},
                id="status",
            ),
            pytest.param(
                {
                    "detail": "The request is not valid",
                    "status_code": 400,
                    "type": "https://example.com/problems/invalid",
                    "title": "Invalid request",
                    "instance": "/puppies/",
                    "errors": [types.ErrorDetail(detail="Field required", pointer="#/name")],
                    "extensions": {"balance": 30},
                },
                {
                    "type": "https://example.com/problems/invalid",
                    "title": "Invalid request",
                    "status": 400,
                    "detail": "The request is not valid",
                    "instance": "/puppies/",
                    "errors": [{"detail": "Field required", "pointer": "#/name"}],
                    "balance": 30,
                },
                id="everything",
            ),
        ),
    )
    def test_init(self, kwargs, expected):
        response = APIErrorResponse(**kwargs)

        assert response.status_code == kwargs["status_code"]
        assert response.headers["content-type"] == "application/problem+json"
        assert json.loads(response.body.decode()) == expected

    def test_init_reserved_extension(self):
        with pytest.raises(
            ValueError, match=r"Extension members cannot be named after members of the problem: \['status'\]"
        ):
            APIErrorResponse(status_code=400, extensions={"status": 1})

    def test_render_extensions(self):
        response = APIErrorResponse(status_code=400, extensions={"balance": 30})

        assert response.schema is libraries.default.schemas.core.APIError
        assert json.loads(response.body.decode())["balance"] == 30
