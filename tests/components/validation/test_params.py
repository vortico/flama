import typing

import pytest
from starlette.testclient import TestClient

from flama.applications.flama import Flama

# flake8: noqa


class TestCaseParamsValidation:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Flama()

        @app_.route("/str_path_param/{param}/")
        def str_path_param(param: str):
            return {"param": param}

        @app_.route("/int_path_param/{param}/")
        def int_path_param(param: int):
            return {"param": param}

        @app_.route("/float_path_param/{param}/")
        def float_path_param(param: float):
            return {"param": param}

        @app_.route("/bool_path_param/{param}/")
        def bool_path_param(param: bool):
            return {"param": param}

        @app_.route("/str_query_param/")
        def str_query_param(param: str):
            return {"param": param}

        @app_.route("/int_query_param/")
        def int_query_param(param: int):
            return {"param": param}

        @app_.route("/float_query_param/")
        def float_query_param(param: float):
            return {"param": param}

        @app_.route("/bool_query_param/")
        def bool_query_param(param: bool):
            return {"param": param}

        @app_.route("/str_query_param_with_default/")
        def str_query_param_with_default(param: str = ""):
            return {"param": param}

        @app_.route("/int_query_param_with_default/")
        def int_query_param_with_default(param: int = None):
            return {"param": param}

        @app_.route("/float_query_param_with_default/")
        def float_query_param_with_default(param: float = None):
            return {"param": param}

        @app_.route("/bool_query_param_with_default/")
        def bool_query_param_with_default(param: bool = False):
            return {"param": param}

        @app_.route("/str_query_param_optional/")
        def str_query_param_optional(param: typing.Optional[str] = None):
            return {"param": param}

        @app_.route("/int_query_param_optional/")
        def int_query_param_optional(param: typing.Optional[int] = None):
            return {"param": param}

        @app_.route("/float_query_param_optional/")
        def float_query_param_optional(param: typing.Optional[float] = None):
            return {"param": param}

        @app_.route("/bool_query_param_optional/")
        def bool_query_param_optional(param: typing.Optional[bool] = None):
            return {"param": param}

        @app_.route("/empty/", methods=["POST"])
        def empty(foo):
            return {}

        return app_

    @pytest.fixture(scope="function")
    def client(self, app):
        return TestClient(app)

    @pytest.mark.parametrize(
        "url,value",
        [
            pytest.param("/str_path_param/123/", "123", id="str path param"),
            pytest.param("/int_path_param/123/", 123, id="int path param"),
            pytest.param("/float_path_param/123.321/", 123.321, id="float path param"),
            pytest.param("/bool_path_param/true/", True, id="float path param"),
        ],
    )
    def test_path_param(self, url, value, client):
        response = client.get(url)
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        "url,value",
        [
            pytest.param("/str_query_param/", "123", id="str query param"),
            pytest.param("/int_query_param/", 123, id="int query param"),
            pytest.param("/float_query_param/", 123.321, id="float query param"),
            pytest.param("/bool_query_param/", True, id="bool query param"),
        ],
    )
    def test_query_param(self, url, value, client):
        response = client.get(url, params={"param": value})
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        "url,value",
        [
            pytest.param("/str_query_param_with_default/", "", id="str query param"),
            pytest.param("/int_query_param_with_default/", None, id="int query param"),
            pytest.param("/float_query_param_with_default/", None, id="float query param"),
            pytest.param("/bool_query_param_with_default/", False, id="bool query param"),
        ],
    )
    def test_query_param_with_default(self, url, value, client):
        response = client.get(url, params={"param": value})
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param("/str_query_param_optional/", id="str query param"),
            pytest.param("/int_query_param_optional/", id="int query param"),
            pytest.param("/float_query_param_optional/", id="float query param"),
            pytest.param("/bool_query_param_optional/", id="bool query param"),
        ],
    )
    def test_query_param_optional(self, url, client):
        response = client.get(url)
        assert response.json() == {"param": None}

    def test_wrong_query_param(self, client):
        response = client.get("/int_query_param/?param=foo")
        assert response.status_code == 400

    def test_wrong_path_param(self, client):
        response = client.get("/int_path_param/foo/")
        assert response.status_code == 400

    def test_no_type_param(self, client):
        response = client.post("/empty/", json={"name": "perdy"})
        assert response.status_code == 400
