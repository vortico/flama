from unittest.mock import Mock, call, mock_open, patch

import pytest

from flama import Flama, pagination, schemas
from flama.schemas.modules import SchemaModule


class TestCaseSchemaModule:
    @pytest.fixture
    def module(self):
        return SchemaModule(Flama(), title="title", version="0.1.0", description="Foo")

    def test_init(self):
        app = Mock(spec=Flama)
        title = "title"
        version = "0.1.0"
        description = "Foo"

        module = SchemaModule(app, title, version, description, "/schema/", "/docs/")

        assert module.app == app
        assert module.title == title
        assert module.version == version
        assert module.description == description
        assert app.add_route.call_count == 2

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

    def test_view_schema(self, client):
        response = client.get("/schema/")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/vnd.oai.openapi"

    def test_view_docs(self, client):
        response = client.get("/docs/")
        assert response.status_code == 200
