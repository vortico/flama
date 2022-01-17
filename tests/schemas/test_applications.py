from unittest.mock import call, mock_open, patch


class TestCaseAppSchemaMixin:
    def test_view_schema(self, client):
        response = client.get("/schema/")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/vnd.oai.openapi"


class TestCaseAppDocsMixin:
    def test_view_docs(self, client):
        with patch("flama.schemas.applications.Template") as mock_template, patch(
            "flama.schemas.applications.open", mock_open(read_data="foo")
        ) as file_mock:
            mock_template.return_value.substitute.return_value = "bar"
            response = client.get("/docs/")

        assert response.status_code == 200
        assert file_mock.call_count == 1
        assert file_mock.call_args_list[0][0][0].endswith("flama/templates/swagger_ui.html")
        assert mock_template.call_args_list == [call("foo")]
        assert response.content == b"bar"


class TestCaseAppRedocMixin:
    def test_view_redoc(self, client):
        with patch("flama.schemas.applications.Template") as mock_template, patch(
            "flama.schemas.applications.open", mock_open(read_data="foo")
        ) as file_mock:
            mock_template.return_value.substitute.return_value = "bar"
            response = client.get("/redoc/")

        assert response.status_code == 200
        assert file_mock.call_count == 1
        assert file_mock.call_args_list[0][0][0].endswith("flama/templates/redoc.html")
        assert mock_template.call_args_list == [call("foo")]
        assert response.content == b"bar"
