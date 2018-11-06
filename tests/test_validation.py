import pytest
from starlette.testclient import TestClient

from starlette_api.applications import Starlette
from starlette_api.schema import types, validators


class User(types.Type):
    name = validators.String(max_length=10)
    age = validators.Integer(minimum=0, allow_null=True, default=None)


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


@app.route("/type_body_param/", methods=["POST"])
def type_body_param(user: User):
    return {"user": dict(user)}


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

    def test_str_query_param(self, client):
        response = client.get("/str_query_param/?param=123")
        assert response.json() == {"param": "123"}

        response = client.get("/str_query_param/")
        assert response.json() == {"param": 'The "param" field is required.'}

    def test_str_query_param_with_default(self, client):
        response = client.get("/str_query_param_with_default/?param=123")
        assert response.json() == {"param": "123"}

        response = client.get("/str_query_param_with_default/")
        assert response.json() == {"param": ""}

    def test_int_query_param(self, client):
        response = client.get("/int_query_param/?param=123")
        assert response.json() == {"param": 123}

        response = client.get("/int_query_param/")
        assert response.json() == {"param": 'The "param" field is required.'}

    def test_int_query_param_with_default(self, client):
        response = client.get("/int_query_param_with_default/?param=123")
        assert response.json() == {"param": 123}

        response = client.get("/int_query_param_with_default/")
        assert response.json() == {"param": None}

    def test_bool_query_param(self, client):
        response = client.get("/bool_query_param/?param=true")
        assert response.json() == {"param": True}

        response = client.get("/bool_query_param/?param=false")
        assert response.json() == {"param": False}

        response = client.get("/bool_query_param/")
        assert response.json() == {"param": 'The "param" field is required.'}

    def test_bool_query_param_with_default(self, client):
        response = client.get("/bool_query_param_with_default/?param=true")
        assert response.json() == {"param": True}

        response = client.get("/bool_query_param_with_default/?param=false")
        assert response.json() == {"param": False}

        response = client.get("/bool_query_param_with_default/")
        assert response.json() == {"param": False}

    def test_type_body_param(self, client):
        response = client.post("/type_body_param/", json={"name": "tom"})
        assert response.json() == {"user": {"name": "tom", "age": None}}

        response = client.post("/type_body_param/", json={"name": "x" * 100})
        assert response.status_code == 400
        assert response.json() == {"name": "Must have no more than 10 characters."}

        response = client.post("/type_body_param/", json={})
        assert response.status_code == 400
        assert response.json() == {"name": 'The "name" field is required.'}
