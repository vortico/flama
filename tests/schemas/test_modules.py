from unittest.mock import Mock, call, mock_open, patch

import pytest

from flama import Flama, pagination, schemas
from flama.schemas.modules import SchemaModule


class TestCaseSchemaModule:
    @pytest.fixture
    def module(self):
        return SchemaModule(Flama())

    def test_init(self):
        app = Mock(spec=Flama)
        title = "title"
        version = "1.0.0"
        description = "Foo"

        module = SchemaModule(app, title, version, description)

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
                title="",
                version="",
                description="",
                schemas={**schemas.schemas.SCHEMAS, **pagination.paginator.schemas},
            )
        ]

    def test_schema(self, module):
        assert module.schema == {
            "openapi": "3.0.3",
            "info": {"title": "", "version": "", "description": ""},
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
        with patch("flama.schemas.modules.Template") as mock_template, patch(
            "flama.schemas.modules.open", mock_open(read_data="foo")
        ) as file_mock:
            mock_template.return_value.substitute.return_value = "bar"
            response = client.get("/docs/")

        assert response.status_code == 200
        assert file_mock.call_count == 1
        assert file_mock.call_args_list[0][0][0].endswith("flama/templates/swagger_ui.html")
        assert mock_template.call_args_list == [call("foo")]
        assert response.content == b"bar"

    def test_view_redoc(self, client):
        with patch("flama.schemas.modules.Template") as mock_template, patch(
            "flama.schemas.modules.open", mock_open(read_data="foo")
        ) as file_mock:
            mock_template.return_value.substitute.return_value = "bar"
            response = client.get("/redoc/")

        assert response.status_code == 200
        assert file_mock.call_count == 1
        assert file_mock.call_args_list[0][0][0].endswith("flama/templates/redoc.html")
        assert mock_template.call_args_list == [call("foo")]
        assert response.content == b"bar"
