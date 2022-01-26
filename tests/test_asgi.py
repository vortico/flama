import pytest

from flama import http, websockets


class TestCaseASGI:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/request/")
        async def get_request(request: http.Request):
            return {
                "method": str(request.method),
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": (await request.body()).decode("utf-8"),
            }

        @app.websocket_route("/websocket/")
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


class TestCaseMethodComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/method/", methods=["GET", "POST"])
        def get_method(method: http.Method):
            return {"method": str(method)}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("/method/", "get", {"method": "GET"}, id="get"),
            pytest.param("/method/", "post", {"method": "POST"}, id="post"),
        ],
    )
    def test_method(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseURLComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/url/")
        def get_url(url: http.URL):
            return {"url": str(url), "components": url.components}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param(
                "http://example.com/url/",
                "get",
                {
                    "url": "http://example.com/url/",
                    "components": ["http", "example.com", "/url/", "", ""],
                },
                id="http",
            ),
            pytest.param(
                "https://example.com/url/",
                "get",
                {
                    "url": "https://example.com/url/",
                    "components": ["https", "example.com", "/url/", "", ""],
                },
                id="https",
            ),
            pytest.param(
                "http://example.com:123/url/",
                "get",
                {
                    "url": "http://example.com:123/url/",
                    "components": ["http", "example.com:123", "/url/", "", ""],
                },
                id="http_port",
            ),
            pytest.param(
                "https://example.com:123/url/",
                "get",
                {
                    "url": "https://example.com:123/url/",
                    "components": ["https", "example.com:123", "/url/", "", ""],
                },
                id="https_port",
            ),
            pytest.param(
                "http://example.com/url/?a=1",
                "get",
                {
                    "url": "http://example.com/url/?a=1",
                    "components": ["http", "example.com", "/url/", "a=1", ""],
                },
                id="query_param",
            ),
        ],
    )
    def test_url(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseSchemeComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/scheme/")
        def get_scheme(scheme: http.Scheme):
            return {"scheme": scheme}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("http://example.com/scheme/", "get", {"scheme": "http"}, id="http"),
            pytest.param("https://example.com/scheme/", "get", {"scheme": "https"}, id="https"),
        ],
    )
    def test_scheme(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseHostComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/host/")
        def get_host(host: http.Host):
            return {"host": host}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("http://example.com/host/", "get", {"host": "example.com"}, id="host"),
            pytest.param("http://example.com:123/host/", "get", {"host": "example.com"}, id="host_and_port"),
        ],
    )
    def test_host(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCasePortComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/port/")
        def get_port(port: http.Port):
            return {"port": port}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("http://example.com/port/", "get", {"port": 80}, id="http"),
            pytest.param("https://example.com/port/", "get", {"port": 443}, id="https"),
            pytest.param("http://example.com:123/port/", "get", {"port": 123}, id="http_custom"),
            pytest.param("https://example.com:123/port/", "get", {"port": 123}, id="https_custom"),
        ],
    )
    def test_port(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCasePathComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/path/")
        def get_path(path: http.Path):
            return {"path": path}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("/path/", "get", {"path": "/path/"}),
        ],
    )
    def test_path(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseQueryStringComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/query_string/")
        def get_query_string(query_string: http.QueryString):
            return {"query_string": query_string}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("/query_string/", "get", {"query_string": ""}, id="empty"),
            pytest.param("/query_string/?a=1&a=2&b=3", "get", {"query_string": "a=1&a=2&b=3"}, id="params"),
        ],
    )
    def test_query_string(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseQueryParamsComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/query_params/")
        def get_query_params(query_string: http.QueryString, query_params: http.QueryParams):
            return {"query_params": dict(query_params)}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("/query_params/", "get", {"query_params": {}}, id="empty"),
            pytest.param("/query_params/?a=1&a=2&b=3", "get", {"query_params": {"a": "2", "b": "3"}}, id="params"),
        ],
    )
    def test_query_params(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseQueryParamComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/page_query_param/")
        def get_page_query_param(page: http.QueryParam):
            return {"page": page}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("/page_query_param/", "get", {"page": None}, id="empty"),
            pytest.param("/page_query_param/?page=123", "get", {"page": "123"}, id="once"),
            pytest.param("/page_query_param/?page=123&page=456", "get", {"page": "456"}, id="multiple"),
        ],
    )
    def test_query_param(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseHeadersComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/headers/", methods=["GET", "POST"])
        def get_headers(headers: http.Headers):
            return {"headers": dict(headers)}

    @pytest.mark.parametrize(
        "path,method,request_kwargs,expected",
        [
            pytest.param(
                "http://example.com/headers/",
                "get",
                {},
                {
                    "headers": {
                        "accept": "*/*",
                        "accept-encoding": "gzip, deflate",
                        "connection": "keep-alive",
                        "host": "example.com",
                        "user-agent": "testclient",
                    }
                },
                id="default",
            ),
            pytest.param(
                "http://example.com/headers/",
                "get",
                {"headers": {"X-Example-Header": "example"}},
                {
                    "headers": {
                        "accept": "*/*",
                        "accept-encoding": "gzip, deflate",
                        "connection": "keep-alive",
                        "host": "example.com",
                        "user-agent": "testclient",
                        "x-example-header": "example",
                    }
                },
                id="custom",
            ),
            pytest.param(
                "http://example.com/headers/",
                "get",
                {"data": {"a": 1}},
                {
                    "headers": {
                        "accept": "*/*",
                        "accept-encoding": "gzip, deflate",
                        "connection": "keep-alive",
                        "content-length": "3",
                        "content-type": "application/x-www-form-urlencoded",
                        "host": "example.com",
                        "user-agent": "testclient",
                    }
                },
                id="content_length",
            ),
        ],
    )
    def test_headers(self, client, path, method, request_kwargs, expected):
        response = client.request(method, path, **dict(request_kwargs))
        assert response.json() == expected


class TestCaseHeaderComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/accept_header/")
        def get_accept_header(accept: http.Header):
            return {"accept": accept}

        @app.route("/missing_header/")
        def get_missing_header(missing: http.Header):
            return {"missing": missing}

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            pytest.param("/accept_header/", "get", {"accept": "*/*"}, id="accept_header"),
            pytest.param("/missing_header/", "get", {"missing": None}, id="missing_header"),
        ],
    )
    def test_header(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseBodyComponent:
    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/body/", methods=["GET", "POST"])
        def get_body(body: http.Body):
            return {"body": body.decode("utf-8")}

    @pytest.mark.parametrize(
        "path,method,request_kwargs,expected",
        [
            pytest.param("/body/", "post", {"data": "content"}, {"body": "content"}),
        ],
    )
    def test_header(self, client, path, method, request_kwargs, expected):
        response = client.request(method, path, **dict(request_kwargs))
        assert response.json() == expected
