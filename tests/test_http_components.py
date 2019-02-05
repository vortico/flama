import pytest
from pytest import param
from starlette.testclient import TestClient

from starlette_api import http
from starlette_api.applications import Starlette

app = Starlette()


@app.route("/request/")
async def get_request(request: http.Request):
    return {
        "method": str(request.method),
        "url": str(request.url),
        "headers": dict(request.headers),
        "body": (await request.body()).decode("utf-8"),
    }


@app.route("/method/", methods=["GET", "POST"])
def get_method(method: http.Method):
    return {"method": str(method)}


@app.route("/scheme/")
def get_scheme(scheme: http.Scheme):
    return {"scheme": scheme}


@app.route("/host/")
def get_host(host: http.Host):
    return {"host": host}


@app.route("/port/")
def get_port(port: http.Port):
    return {"port": port}


@app.route("/path/")
def get_path(path: http.Path):
    return {"path": path}


@app.route("/query_string/")
def get_query_string(query_string: http.QueryString):
    return {"query_string": query_string}


@app.route("/query_params/")
def get_query_params(query_string: http.QueryString, query_params: http.QueryParams):
    return {"query_params": dict(query_params)}


@app.route("/page_query_param/")
def get_page_query_param(page: http.QueryParam):
    return {"page": page}


@app.route("/url/")
def get_url(url: http.URL):
    return {"url": url, "url.components": url.components}


@app.route("/body/", methods=["GET", "POST"])
def get_body(body: http.Body):
    return {"body": body.decode("utf-8")}


@app.route("/headers/", methods=["GET", "POST"])
def get_headers(headers: http.Headers):
    return {"headers": dict(headers)}


@app.route("/accept_header/")
def get_accept_header(accept: http.Header):
    return {"accept": accept}


@app.route("/missing_header/")
def get_missing_header(missing: http.Header):
    return {"missing": missing}


@app.route("/path_params/{example}/", methods=["GET", "POST"])
def get_path_params(params: http.PathParams):
    return {"params": params}


@app.route("/request_data/", methods=["POST"])
async def get_request_data(data: http.RequestData):
    try:
        data = {
            key: value
            if not hasattr(value, "filename")
            else {"filename": value.filename, "content": (await value.read()).decode("utf-8")}
            for key, value in data.items()
        }
    except Exception:
        pass

    return {"data": data}


@app.route("/return_string/")
def return_string(data: http.RequestData) -> str:
    return "<html><body>example content</body></html>"


@app.route("/return_data/")
def return_data(data: http.RequestData) -> dict:
    return {"example": "content"}


@app.route("/return_response/")
def return_response(data: http.RequestData) -> http.Response:
    return http.JSONResponse({"example": "content"})


@app.route("/return_unserializable_json/")
def return_unserializable_json() -> dict:
    class Dummy:
        pass

    return {"dummy": Dummy()}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestCaseHttp:
    def test_request(self, client):
        expected_response = {
            "method": "GET",
            "url": "http://testserver/request/",
            "headers": {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate",
                "connection": "keep-alive",
                "host": "testserver",
                "user-agent": "testclient",
            },
            "body": "",
        }

        response = client.get("/request/")

        assert response.json() == expected_response, response.content

    def test_method(self, client):
        response = client.get("/method/")
        assert response.json() == {"method": "GET"}
        response = client.post("/method/")
        assert response.json() == {"method": "POST"}

    def test_scheme(self, client):
        response = client.get("http://example.com/scheme/")
        assert response.json() == {"scheme": "http"}
        response = client.get("https://example.com/scheme/")
        assert response.json() == {"scheme": "https"}

    def test_host(self, client):
        response = client.get("http://example.com/host/")
        assert response.json() == {"host": "example.com"}

    def test_port(self, client):
        response = client.get("http://example.com/port/")
        assert response.json() == {"port": 80}
        response = client.get("https://example.com/port/")
        assert response.json() == {"port": 443}
        response = client.get("http://example.com:123/port/")
        assert response.json() == {"port": 123}
        response = client.get("https://example.com:123/port/")
        assert response.json() == {"port": 123}

    def test_path(self, client):
        response = client.get("/path/")
        assert response.json() == {"path": "/path/"}

    def test_query_string(self, client):
        response = client.get("/query_string/")
        assert response.json() == {"query_string": ""}
        response = client.get("/query_string/?a=1&a=2&b=3")
        assert response.json() == {"query_string": "a=1&a=2&b=3"}

    def test_query_params(self, client):
        response = client.get("/query_params/")
        assert response.json() == {"query_params": {}}
        response = client.get("/query_params/?a=1&a=2&b=3")
        assert response.json() == {"query_params": {"a": "1", "b": "3"}}

    def test_single_query_param(self, client):
        response = client.get("/page_query_param/")
        assert response.json() == {"page": None}
        response = client.get("/page_query_param/?page=123")
        assert response.json() == {"page": "123"}
        response = client.get("/page_query_param/?page=123&page=456")
        assert response.json() == {"page": "123"}

    def test_url(self, client):
        response = client.get("http://example.com/url/")
        assert response.json() == {
            "url": "http://example.com/url/",
            "url.components": ["http", "example.com", "/url/", "", "", ""],
        }
        response = client.get("https://example.com/url/")
        assert response.json() == {
            "url": "https://example.com/url/",
            "url.components": ["https", "example.com", "/url/", "", "", ""],
        }
        response = client.get("http://example.com:123/url/")
        assert response.json() == {
            "url": "http://example.com:123/url/",
            "url.components": ["http", "example.com:123", "/url/", "", "", ""],
        }
        response = client.get("https://example.com:123/url/")
        assert response.json() == {
            "url": "https://example.com:123/url/",
            "url.components": ["https", "example.com:123", "/url/", "", "", ""],
        }
        response = client.get("http://example.com/url/?a=1")
        assert response.json() == {
            "url": "http://example.com/url/?a=1",
            "url.components": ["http", "example.com", "/url/", "", "a=1", ""],
        }

    def test_body(self, client):
        response = client.post("/body/", data="content")
        assert response.json() == {"body": "content"}

    def test_headers(self, client):
        response = client.get("http://example.com/headers/")
        assert response.json() == {
            "headers": {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate",
                "connection": "keep-alive",
                "host": "example.com",
                "user-agent": "testclient",
            }
        }
        response = client.get("http://example.com/headers/", headers={"X-Example-Header": "example"})
        assert response.json() == {
            "headers": {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate",
                "connection": "keep-alive",
                "host": "example.com",
                "user-agent": "testclient",
                "x-example-header": "example",
            }
        }

        response = client.post("http://example.com/headers/", data={"a": 1})
        assert response.json() == {
            "headers": {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate",
                "connection": "keep-alive",
                "content-length": "3",
                "content-type": "application/x-www-form-urlencoded",
                "host": "example.com",
                "user-agent": "testclient",
            }
        }

    def test_accept_header(self, client):
        response = client.get("/accept_header/")
        assert response.json() == {"accept": "*/*"}

    def test_missing_header(self, client):
        response = client.get("/missing_header/")
        assert response.json() == {"missing": None}

    def test_path_params(self, client):
        response = client.get("/path_params/abc/")
        assert response.json() == {"params": {"example": "abc"}}
        response = client.get("/path_params/a%20b%20c/")
        assert response.json() == {"params": {"example": "a b c"}}
        response = client.get("/path_params/abc/def/")
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "request_params,response_status,response_json",
        [
            # JSON
            param({"json": {"abc": 123}}, 200, {"data": {"abc": 123}}, id="valid json body"),
            param({}, 200, {"data": None}, id="empty json body"),
            # Urlencoding
            param({"data": {"abc": 123}}, 200, {"data": {"abc": "123"}}, id="valid urlencoded body"),
            param(
                {"headers": {"content-type": "application/x-www-form-urlencoded"}},
                200,
                {"data": None},
                id="empty urlencoded body",
            ),
            # Misc
            param({"data": b"...", "headers": {"content-type": "unknown"}}, 415, None, id="unknown body type"),
            param(
                {"data": b"...", "headers": {"content-type": "application/json"}}, 400, None, id="json parse failure"
            ),
        ],
    )
    def test_request_data(self, request_params, response_status, response_json, client):
        response = client.post("/request_data/", **request_params)
        assert response.status_code == response_status, str(response.content)
        if response_json is not None:
            assert response.json() == response_json

    def test_multipart_request_data(self, client):
        response = client.post("/request_data/", files={"a": ("b", "123")}, data={"b": "42"})
        assert response.status_code == 200
        assert response.json() == {"data": {"a": {"filename": "b", "content": "123"}, "b": "42"}}

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

    def test_headers_type(self, client):
        h = http.Headers([("a", "123"), ("A", "456"), ("b", "789")])
        assert "a" in h
        assert "A" in h
        assert "b" in h
        assert "B" in h
        assert "c" not in h
        assert h["a"] == "123"
        assert h.get_list("a") == ["123", "456"]
        assert h.keys() == ["a", "a", "b"]
        assert h.values() == ["123", "456", "789"]
        assert h.items() == [("a", "123"), ("a", "456"), ("b", "789")]
        assert list(h) == [("a", "123"), ("a", "456"), ("b", "789")]
        assert dict(h) == {"a": "123", "b": "789"}
        assert repr(h) == "Headers([('a', '123'), ('a', '456'), ('b', '789')])"
        assert http.Headers({"a": "123", "b": "456"}) == http.Headers([("a", "123"), ("b", "456")])
        assert http.Headers({"a": "123", "b": "456"}) == {"B": "456", "a": "123"}
        assert http.Headers({"a": "123", "b": "456"}) == [("B", "456"), ("a", "123")]
        assert {"B": "456", "a": "123"} == http.Headers({"a": "123", "b": "456"})
        assert [("B", "456"), ("a", "123")] == http.Headers({"a": "123", "b": "456"})

    def test_queryparams_type(self, client):
        q = http.QueryParams([("a", "123"), ("a", "456"), ("b", "789")])
        assert "a" in q
        assert "A" not in q
        assert "c" not in q
        assert q["a"] == "123"
        assert q.get_list("a") == ["123", "456"]
        assert q.keys() == ["a", "a", "b"]
        assert q.values() == ["123", "456", "789"]
        assert q.items() == [("a", "123"), ("a", "456"), ("b", "789")]
        assert list(q) == [("a", "123"), ("a", "456"), ("b", "789")]
        assert dict(q) == {"a": "123", "b": "789"}
        assert repr(q) == "QueryParams([('a', '123'), ('a', '456'), ('b', '789')])"
        assert http.QueryParams({"a": "123", "b": "456"}) == http.QueryParams([("a", "123"), ("b", "456")])
        assert http.QueryParams({"a": "123", "b": "456"}) == {"b": "456", "a": "123"}
        assert http.QueryParams({"a": "123", "b": "456"}) == [("b", "456"), ("a", "123")]
        assert {"b": "456", "a": "123"} == http.QueryParams({"a": "123", "b": "456"})
        assert [("b", "456"), ("a", "123")] == http.QueryParams({"a": "123", "b": "456"})
