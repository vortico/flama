import marshmallow
import pytest
from starlette.testclient import TestClient

from starlette_api.applications import Starlette
from starlette_api.pagination import paginator


class OutputSchema(marshmallow.Schema):
    value = marshmallow.fields.Integer()


class TestLimitOffsetResponse:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Starlette(title="Foo", version="0.1", description="Bar", schema="/schema/")

        @app_.route("/limit-offset/", methods=["GET"])
        @paginator.limit_offset
        def page_number(**kwargs) -> OutputSchema(many=True):
            return [{"value": i} for i in range(25)]

        return app_

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_invalid_view(self, app):
        with pytest.raises(TypeError, match=r"Paginated views must define \*\*kwargs param"):

            @paginator.limit_offset
            def invalid():
                ...

    def test_pagination_params(self, app):
        schema = app.schema["paths"]["/limit-offset/"]["get"]
        parameters = schema.get("parameters", {})

        assert parameters == [
            {
                "name": "offset",
                "in": "query",
                "required": False,
                "schema": {"default": None, "type": "integer", "format": "int32", "nullable": True},
            },
            {"name": "count", "in": "query", "required": False, "schema": {"type": "boolean", "default": True}},
            {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {"default": None, "type": "integer", "format": "int32", "nullable": True},
            },
        ]

    def test_default_params(self, client):
        response = client.get("/limit-offset/")
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "meta": {"limit": 10, "offset": 0, "count": 25},
            "data": [{"value": i} for i in range(10)],
        }

    def test_default_offset_explicit_limit(self, client):
        response = client.get("/limit-offset/", params={"limit": 5})
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"limit": 5, "offset": 0, "count": 25},
            "data": [{"value": i} for i in range(5)],
        }

    def test_default_limit_explicit_offset(self, client):
        response = client.get("/limit-offset/", params={"offset": 5})
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"limit": 10, "offset": 5, "count": 25},
            "data": [{"value": i} for i in range(5, 15)],
        }

    def test_explicit_params(self, client):
        response = client.get("/limit-offset/", params={"offset": 5, "limit": 20})
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"limit": 20, "offset": 5, "count": 25},
            "data": [{"value": i} for i in range(5, 25)],
        }

    def test_no_count(self, client):
        response = client.get("/limit-offset/", params={"count": False})
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"limit": 10, "offset": 0, "count": None},
            "data": [{"value": i} for i in range(10)],
        }


class TestPageNumberResponse:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Starlette(title="Foo", version="0.1", description="Bar", schema="/schema/")

        @app_.route("/page-number/", methods=["GET"])
        @paginator.page_number
        def page_number(**kwargs) -> OutputSchema(many=True):
            return [{"value": i} for i in range(25)]

        return app_

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_invalid_view(self, app):
        with pytest.raises(TypeError, match=r"Paginated views must define \*\*kwargs param"):

            @paginator.page_number
            def invalid():
                ...

    def test_pagination_params(self, app):
        schema = app.schema["paths"]["/page-number/"]["get"]
        parameters = schema.get("parameters", {})

        assert parameters == [
            {
                "name": "page_size",
                "in": "query",
                "required": False,
                "schema": {"default": None, "type": "integer", "format": "int32", "nullable": True},
            },
            {"name": "count", "in": "query", "required": False, "schema": {"type": "boolean", "default": True}},
            {
                "name": "page",
                "in": "query",
                "required": False,
                "schema": {"default": None, "type": "integer", "format": "int32", "nullable": True},
            },
        ]

    def test_default_params(self, client):
        response = client.get("/page-number/")
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"page": 1, "page_size": 10, "count": 25},
            "data": [{"value": i} for i in range(10)],
        }

    def test_default_page_explicit_size(self, client):
        response = client.get("/page-number/", params={"page_size": 5})
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"page": 1, "page_size": 5, "count": 25},
            "data": [{"value": i} for i in range(5)],
        }

    def test_default_size_explicit_page(self, client):
        response = client.get("/page-number/", params={"page": 2})
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"page": 2, "page_size": 10, "count": 25},
            "data": [{"value": i} for i in range(10, 20)],
        }

    def test_explicit_params(self, client):
        response = client.get("/page-number/", params={"page": 4, "page_size": 5})
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"page": 4, "page_size": 5, "count": 25},
            "data": [{"value": i} for i in range(15, 20)],
        }

    def test_no_count(self, client):
        response = client.get("/page-number/", params={"count": False})
        assert response.status_code == 200
        assert response.json() == {
            "meta": {"page": 1, "page_size": 10, "count": None},
            "data": [{"value": i} for i in range(10)],
        }
