import pytest

from flama import types


class TestCaseMethodComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/method/", methods=["GET", "POST"])
        def get_method(method: types.Method):
            return {"method": str(method)}

    @pytest.mark.parametrize(
        ["path", "method", "expected"],
        [
            pytest.param("/method/", "get", {"method": "GET"}, id="get"),
            pytest.param("/method/", "post", {"method": "POST"}, id="post"),
        ],
    )
    def test_method(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseURLComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/url/")
        def get_url(url: types.URL):
            return {"url": url.url, "components": url.components}

    @pytest.mark.parametrize(
        ["path", "method", "expected"],
        [
            pytest.param(
                "http://example.com/url/",
                "get",
                {
                    "url": "http://example.com/url/",
                    "components": {
                        "scheme": "http",
                        "netloc": "example.com",
                        "path": "/url/",
                        "query": "",
                        "fragment": "",
                        "params": "",
                    },
                },
                id="http",
            ),
            pytest.param(
                "https://example.com/url/",
                "get",
                {
                    "url": "https://example.com/url/",
                    "components": {
                        "scheme": "https",
                        "netloc": "example.com",
                        "path": "/url/",
                        "query": "",
                        "fragment": "",
                        "params": "",
                    },
                },
                id="https",
            ),
            pytest.param(
                "http://example.com:123/url/",
                "get",
                {
                    "url": "http://example.com:123/url/",
                    "components": {
                        "scheme": "http",
                        "netloc": "example.com:123",
                        "path": "/url/",
                        "query": "",
                        "fragment": "",
                        "params": "",
                    },
                },
                id="http_port",
            ),
            pytest.param(
                "https://example.com:123/url/",
                "get",
                {
                    "url": "https://example.com:123/url/",
                    "components": {
                        "scheme": "https",
                        "netloc": "example.com:123",
                        "path": "/url/",
                        "query": "",
                        "fragment": "",
                        "params": "",
                    },
                },
                id="https_port",
            ),
            pytest.param(
                "http://example.com/url/?a=1",
                "get",
                {
                    "url": "http://example.com/url/?a=1",
                    "components": {
                        "scheme": "http",
                        "netloc": "example.com",
                        "path": "/url/",
                        "query": "a=1",
                        "fragment": "",
                        "params": "",
                    },
                },
                id="query_param",
            ),
        ],
    )
    def test_url(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseSchemeComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/scheme/")
        def get_scheme(scheme: types.Scheme):
            return {"scheme": scheme}

    @pytest.mark.parametrize(
        ["path", "method", "expected"],
        [
            pytest.param("http://example.com/scheme/", "get", {"scheme": "http"}, id="http"),
            pytest.param("https://example.com/scheme/", "get", {"scheme": "https"}, id="https"),
        ],
    )
    def test_scheme(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseHostComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/host/")
        def get_host(host: types.Host):
            return {"host": host}

    @pytest.mark.parametrize(
        ["path", "method", "expected"],
        [
            pytest.param("http://example.com/host/", "get", {"host": "example.com"}, id="host"),
            pytest.param("http://example.com:123/host/", "get", {"host": "example.com"}, id="host_and_port"),
        ],
    )
    def test_host(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCasePortComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/port/")
        def get_port(port: types.Port):
            return {"port": port}

    @pytest.mark.parametrize(
        ["path", "method", "expected"],
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
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/path/")
        def get_path(path: types.Path):
            return {"path": path}

    @pytest.mark.parametrize(
        ["path", "method", "expected"],
        [
            pytest.param("/path/", "get", {"path": "/path/"}),
        ],
    )
    def test_path(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseQueryStringComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/query_string/")
        def get_query_string(query_string: types.QueryString):
            return {"query_string": query_string}

    @pytest.mark.parametrize(
        ["path", "method", "expected"],
        [
            pytest.param("/query_string/", "get", {"query_string": ""}, id="empty"),
            pytest.param("/query_string/?a=1&a=2&b=3", "get", {"query_string": "a=1&a=2&b=3"}, id="params"),
        ],
    )
    def test_query_string(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseQueryParamsComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/query_params/")
        def get_query_params(query_string: types.QueryString, query_params: types.QueryParams):
            return {"query_params": dict(query_params)}

    @pytest.mark.parametrize(
        ["path", "method", "expected"],
        [
            pytest.param("/query_params/", "get", {"query_params": {}}, id="empty"),
            pytest.param("/query_params/?a=1&a=2&b=3", "get", {"query_params": {"a": "2", "b": "3"}}, id="params"),
        ],
    )
    def test_query_params(self, client, path, method, expected):
        response = client.request(method, path)
        assert response.json() == expected


class TestCaseHeadersComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/headers/", methods=["GET", "POST"])
        def get_headers(headers: types.Headers):
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


class TestCaseBodyComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/body/", methods=["GET", "POST"])
        def get_body(body: types.Body):
            return {"body": body.decode("utf-8")}

    @pytest.mark.parametrize(
        ["path", "method", "request_kwargs", "expected"],
        [
            pytest.param("/body/", "post", {"content": "content"}, {"body": "content"}, id="default"),
        ],
    )
    def test_body(self, client, path, method, request_kwargs, expected):
        response = client.request(method, path, **dict(request_kwargs))
        assert response.json() == expected
