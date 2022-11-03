from unittest.mock import Mock, call, patch

import pytest

from flama import Flama, pagination, schemas
from flama.schemas.modules import SchemaModule


class TestCaseSchemaModule:
    @pytest.fixture
    def module(self):
        m = SchemaModule("title", "0.1.0", "Foo", schema="/schema/", docs="/docs/")
        m.app = Flama()
        return m

    def test_init(self):
        title = "title"
        version = "0.1.0"
        description = "Foo"

        module = SchemaModule(title, version, description, "/schema/", "/docs/")

        assert module.title == title
        assert module.version == version
        assert module.description == description

    def test_schema_generator(self, module):
        with patch("flama.schemas.modules.SchemaGenerator") as generator_mock:
            module.schema_generator

        assert generator_mock.call_args_list == [
            call(
                title="title",
                version="0.1.0",
                description="Foo",
                schemas={**schemas.schemas.SCHEMAS, **pagination.paginator.schemas},
            )
        ]

    def test_schema(self, module):
        assert module.schema == {
            "openapi": "3.1.0",
            "info": {"title": "title", "version": "0.1.0", "description": "Foo"},
            "paths": {},
            "components": {
                "schemas": {},
                "responses": {},
                "parameters": {},
                "examples": {},
                "requestBodies": {},
                "headers": {},
                "securitySchemes": {},
                "links": {},
                "callbacks": {},
            },
        }

    @pytest.mark.parametrize(
        ["schema", "docs", "exception"],
        (
            pytest.param(False, False, None, id="no_schema_no_docs"),
            pytest.param(True, False, None, id="schema_but_no_docs"),
            pytest.param(
                False, True, AssertionError("Schema path must be defined to use docs view"), id="no_schema_but_docs"
            ),
            pytest.param(True, True, None, id="schema_and_docs"),
        ),
        indirect=["exception"],
    )
    def test_add_routes(self, schema, docs, exception):
        module = SchemaModule("", "", "", schema, docs)
        module.app = Mock(Flama)
        expected_calls = []
        if schema:
            expected_calls.append(call(schema, module.schema_view, methods=["GET"], include_in_schema=False))
        if docs:
            expected_calls.append(call(docs, module.docs_view, methods=["GET"], include_in_schema=False))

        with exception:
            module.add_routes()
            assert module.app.add_route.call_args_list == expected_calls

    def test_view_schema(self, client):
        response = client.request("get", "/schema/")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/vnd.oai.openapi"

    def test_view_docs(self, client):
        response = client.request("get", "/docs/")
        assert response.status_code == 200
