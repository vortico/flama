from unittest.mock import Mock, call, patch

import pytest

from flama import Flama, exceptions, pagination, schemas
from flama.schemas.modules import SchemaModule


class TestCaseSchemaModule:
    @pytest.fixture
    def module(self, openapi_spec):
        m = SchemaModule(openapi=openapi_spec, schema="/schema/", docs="/docs/")
        m.app = Flama()
        return m

    def test_init(self, openapi_spec):
        module = SchemaModule(openapi_spec, schema="/schema/", docs="/docs/")

        assert module.openapi == openapi_spec

    def test_register_schema(self, module, foo_schema):
        assert module.schemas == {}

        module.register_schema("foo", foo_schema)

        assert module.schemas == {"foo": foo_schema}

    def test_schema_generator(self, module):
        with patch("flama.schemas.modules.SchemaGenerator") as generator_mock:
            module.schema_generator

        assert generator_mock.call_args_list == [
            call(
                spec={"info": {"title": "Foo", "version": "1.0.0", "description": "Bar"}},
                schemas={**schemas.schemas.SCHEMAS, **pagination.paginator.schemas},
            )
        ]

    def test_schema(self, module):
        assert module.schema == {
            "openapi": "3.1.0",
            "info": {"title": "Foo", "version": "1.0.0", "description": "Bar"},
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
            pytest.param(
                False,
                False,
                None,
                id="no_schema_no_docs",
            ),
            pytest.param(
                True,
                False,
                None,
                id="schema_but_no_docs",
            ),
            pytest.param(
                False,
                True,
                exceptions.ApplicationError("Docs endpoint needs schema endpoint to be active"),
                id="no_schema_but_docs",
            ),
            pytest.param(
                True,
                True,
                None,
                id="schema_and_docs",
            ),
        ),
        indirect=["exception"],
    )
    def test_add_routes(self, openapi_spec, schema, docs, exception):
        with exception:
            module = SchemaModule(openapi_spec, schema=schema, docs=docs)
            module.app = Mock(Flama)
            expected_calls = []
            if schema:
                expected_calls.append(call(schema, module.schema_view, methods=["GET"], include_in_schema=False))
            if docs:
                expected_calls.append(call(docs, module.docs_view, methods=["GET"], include_in_schema=False))

            module.add_routes()

            assert module.app.add_route.call_args_list == expected_calls

    async def test_view_schema(self, client):
        response = await client.request("get", "/schema/")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/vnd.oai.openapi"

    async def test_view_docs(self, client):
        response = await client.request("get", "/docs/")
        assert response.status_code == 200
