import pytest
from starlette.testclient import TestClient

from starlette_api import http
from starlette_api.applications import Starlette


class TestCaseReturnValidation:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Starlette(schema=None, docs=None)

        @app_.route("/return_string/")
        def return_string(data: http.RequestData) -> str:
            return "<html><body>example content</body></html>"

        @app_.route("/return_data/")
        def return_data(data: http.RequestData) -> dict:
            return {"example": "content"}

        @app_.route("/return_response/")
        def return_response(data: http.RequestData) -> http.Response:
            return http.JSONResponse({"example": "content"})

        @app_.route("/return_unserializable_json/")
        def return_unserializable_json() -> dict:
            class Dummy:
                pass

            return {"dummy": Dummy()}

        return app_

    @pytest.fixture(scope="function")
    def client(self, app):
        return TestClient(app)

    def test_return_string(self, client):
        response = client.get("/return_string/")
        assert response.text == "<html><body>example content</body></html>"

    def test_return_data(self, client):
        response = client.get("/return_data/")
        assert response.json() == {"example": "content"}

    def test_return_response(self, client):
        response = client.get("/return_response/")
        assert response.json() == {"example": "content"}

    def test_return_unserializable_json(self, client):
        with pytest.raises(TypeError, match=r".*Object of type .?Dummy.? is not JSON serializable"):
            client.get("/return_unserializable_json/")
