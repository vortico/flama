import typing

import pytest
from marshmallow import Schema, fields, validate
from starlette.testclient import TestClient

from starlette_api.applications import Starlette


class User(Schema):
    name = fields.String(validate=validate.Length(max=10), required=True)
    age = fields.Integer(minimum=0, missing=None)


app = Starlette()


@app.route("/str_path_param/{param}/")
def str_path_param(param: str):
    return {"param": param}


@app.route("/int_path_param/{param}/")
def int_path_param(param: int):
    return {"param": param}


@app.route("/str_query_param/")
def str_query_param(param: str):
    return {"param": param}


@app.route("/int_query_param/")
def int_query_param(param: int):
    return {"param": param}


@app.route("/bool_query_param/")
def bool_query_param(param: bool):
    return {"param": param}


@app.route("/str_query_param_with_default/")
def str_query_param_with_default(param: str = ""):
    return {"param": param}


@app.route("/int_query_param_with_default/")
def int_query_param_with_default(param: int = None):
    return {"param": param}


@app.route("/bool_query_param_with_default/")
def bool_query_param_with_default(param: bool = False):
    return {"param": param}


@app.route("/str_query_param_optional/")
def str_query_param_optional(param: typing.Optional[str] = None):
    return {"param": param}


@app.route("/int_query_param_optional/")
def int_query_param_optional(param: typing.Optional[int] = None):
    return {"param": param}


@app.route("/bool_query_param_optional/")
def bool_query_param_optional(param: typing.Optional[bool] = None):
    return {"param": param}


@app.route("/type_body_param/", methods=["POST"])
def type_body_param(user: User):
    return {"user": dict(user)}


@app.route("/empty/", methods=["POST"])
def empty(foo):
    return {}


@pytest.fixture
def client():
    return TestClient(app)


class TestCaseValidation:
    def test_str_path_param(self, client):
        response = client.get("/str_path_param/123/")
        assert response.json() == {"param": "123"}

    def test_int_path_param(self, client):
        response = client.get("/int_path_param/123/")
        assert response.json() == {"param": 123}

    def test_wrong_path_param(self, client):
        response = client.get("/int_path_param/foo/")
        assert response.status_code == 400

    def test_str_query_param(self, client):
        response = client.get("/str_query_param/?param=123")
        assert response.json() == {"param": "123"}

        response = client.get("/str_query_param/")
        assert response.json() == {"param": ["Missing data for required field."]}

    def test_str_query_param_with_default(self, client):
        response = client.get("/str_query_param_with_default/?param=123")
        assert response.json() == {"param": "123"}

        response = client.get("/str_query_param_with_default/")
        assert response.json() == {"param": ""}

    def test_str_query_param_optional(self, client):
        response = client.get("/str_query_param_optional/?param=123")
        assert response.json() == {"param": "123"}

        response = client.get("/str_query_param_optional/")
        assert response.json() == {"param": None}

    def test_int_query_param(self, client):
        response = client.get("/int_query_param/?param=123")
        assert response.json() == {"param": 123}

        response = client.get("/int_query_param/")
        assert response.json() == {"param": ["Missing data for required field."]}

    def test_int_query_param_with_default(self, client):
        response = client.get("/int_query_param_with_default/?param=123")
        assert response.json() == {"param": 123}

        response = client.get("/int_query_param_with_default/")
        assert response.json() == {"param": None}

    def test_int_query_param_optional(self, client):
        response = client.get("/int_query_param_optional/?param=123")
        assert response.json() == {"param": 123}

        response = client.get("/int_query_param_optional/")
        assert response.json() == {"param": None}

    def test_bool_query_param(self, client):
        response = client.get("/bool_query_param/?param=true")
        assert response.json() == {"param": True}

        response = client.get("/bool_query_param/?param=false")
        assert response.json() == {"param": False}

        response = client.get("/bool_query_param/")
        assert response.json() == {"param": ["Missing data for required field."]}

    def test_bool_query_param_with_default(self, client):
        response = client.get("/bool_query_param_with_default/?param=true")
        assert response.json() == {"param": True}

        response = client.get("/bool_query_param_with_default/?param=false")
        assert response.json() == {"param": False}

        response = client.get("/bool_query_param_with_default/")
        assert response.json() == {"param": False}

    def test_bool_query_param_optional(self, client):
        response = client.get("/bool_query_param_optional/?param=true")
        assert response.json() == {"param": True}

        response = client.get("/bool_query_param_optional/?param=false")
        assert response.json() == {"param": False}

        response = client.get("/bool_query_param_optional/")
        assert response.json() == {"param": None}

    def test_wrong_query_param(self, client):
        response = client.get("/int_query_param/?param=foo")
        assert response.status_code == 400

    def test_type_body_param(self, client):
        response = client.post("/type_body_param/", json={"name": "perdy"})
        assert response.json() == {"user": {"name": "perdy", "age": None}}

        response = client.post("/type_body_param/", json={"name": "x" * 100})
        assert response.status_code == 400
        assert response.json() == {"name": ["Longer than maximum length 10."]}

        response = client.post("/type_body_param/", json={})
        assert response.status_code == 400
        assert response.json() == {"name": ["Missing data for required field."]}

    def test_no_type_param(self, client):
        response = client.post("/empty/", json={"name": "perdy"})
        assert response.status_code == 400
