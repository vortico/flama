import pytest
from starlette.testclient import TestClient

from flama.applications.flama import Flama
from flama.types import http, websockets

# flake8: noqa


class TestCaseASGI:
    @pytest.fixture(scope="class")
    def app(self):  # noqa
        app_ = Flama(schema=None, docs=None)

        @app_.route("/method/", methods=["GET", "POST"])
        def get_method(method: http.Method):
            return {"method": str(method)}

        @app_.route("/url/")
        def get_url(url: http.URL):
            return {"url": str(url), "components": url.components}

        @app_.route("/scheme/")
        def get_scheme(scheme: http.Scheme):
            return {"scheme": scheme}

        @app_.route("/host/")
        def get_host(host: http.Host):
            return {"host": host}

        @app_.route("/port/")
        def get_port(port: http.Port):
            return {"port": port}

        @app_.route("/path/")
        def get_path(path: http.Path):
            return {"path": path}

        @app_.route("/query_string/")
        def get_query_string(query_string: http.QueryString):
            return {"query_string": query_string}

        @app_.route("/query_params/")
        def get_query_params(query_string: http.QueryString, query_params: http.QueryParams):
            return {"query_params": dict(query_params)}

        @app_.route("/page_query_param/")
        def get_page_query_param(page: http.QueryParam):
            return {"page": page}

        @app_.route("/headers/", methods=["GET", "POST"])
        def get_headers(headers: http.Headers):
            return {"headers": dict(headers)}

        @app_.route("/accept_header/")
        def get_accept_header(accept: http.Header):
            return {"accept": accept}

        @app_.route("/missing_header/")
        def get_missing_header(missing: http.Header):
            return {"missing": missing}

        @app_.route("/body/", methods=["GET", "POST"])
        def get_body(body: http.Body):
            return {"body": body.decode("utf-8")}

        @app_.route("/request/")
        async def get_request(request: http.Request):
            return {
                "method": str(request.method),
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": (await request.body()).decode("utf-8"),
            }

        @app_.websocket_route("/websocket/")
        async def get_websocket(websocket: websockets.WebSocket):
            await websocket.accept()
            await websocket.send_json(
                {
                    "url": str(websocket.url),
                    "headers": dict(websocket.headers),
                    "state": str(websocket.client_state.name),
                }
            )
            await websocket.close()

        return app_

    @pytest.fixture(scope="function")
    def client(self, app):
        return TestClient(app)

    def test_method(self, client):
        response = client.get("/method/")
        assert response.json() == {"method": "GET"}
        response = client.post("/method/")
        assert response.json() == {"method": "POST"}

    def test_url(self, client):
        response = client.get("http://example.com/url/")
        assert response.json() == {
            "url": "http://example.com/url/",
            "components": ["http", "example.com", "/url/", "", ""],
        }
        response = client.get("https://example.com/url/")
        assert response.json() == {
            "url": "https://example.com/url/",
            "components": ["https", "example.com", "/url/", "", ""],
        }
        response = client.get("http://example.com:123/url/")
        assert response.json() == {
            "url": "http://example.com:123/url/",
            "components": ["http", "example.com:123", "/url/", "", ""],
        }
        response = client.get("https://example.com:123/url/")
        assert response.json() == {
            "url": "https://example.com:123/url/",
            "components": ["https", "example.com:123", "/url/", "", ""],
        }
        response = client.get("http://example.com/url/?a=1")
        assert response.json() == {
            "url": "http://example.com/url/?a=1",
            "components": ["http", "example.com", "/url/", "a=1", ""],
        }

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
        assert response.json() == {"query_params": {"a": "2", "b": "3"}}

    def test_single_query_param(self, client):
        response = client.get("/page_query_param/")
        assert response.json() == {"page": None}
        response = client.get("/page_query_param/?page=123")
        assert response.json() == {"page": "123"}
        response = client.get("/page_query_param/?page=123&page=456")
        assert response.json() == {"page": "456"}

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

    def test_body(self, client):
        response = client.post("/body/", data="content")
        assert response.json() == {"body": "content"}

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

    def test_websocket(self, client):
        expected_response = {
            "headers": {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate",
                "connection": "upgrade",
                "host": "testserver",
                "sec-websocket-key": "testserver==",
                "sec-websocket-version": "13",
                "user-agent": "testclient",
            },
            "state": "CONNECTED",
            "url": "ws://testserver/websocket/",
        }

        with client.websocket_connect("/websocket/") as ws:
            response = ws.receive_json()

        assert response == expected_response, response
