import pytest

from flama import types
from flama.exceptions import ApplicationError
from flama.http.data_structures import Address, Headers, QueryParams, State
from flama.http.requests.connection import HTTPConnection
from flama.url import URL


class TestCaseHTTPConnection:
    @pytest.fixture
    def scope(self):
        return types.Scope(
            {
                "type": "http",
                "method": "GET",
                "path": "/test",
                "query_string": b"foo=bar&baz=1",
                "headers": [
                    (b"host", b"example.com"),
                    (b"content-type", b"text/html"),
                    (b"cookie", b"session=abc123; theme=dark"),
                ],
                "server": ("example.com", 443),
                "scheme": "https",
                "root_path": "",
                "path_params": {"id": "42"},
                "client": ("192.168.1.1", 12345),
            }
        )

    @pytest.fixture
    def conn(self, scope):
        return HTTPConnection(scope)

    @pytest.mark.parametrize(
        ["scope_type", "exception"],
        [
            pytest.param("http", None, id="http"),
            pytest.param("websocket", None, id="websocket"),
            pytest.param("lifespan", RuntimeError("Request scope type must be 'http' or 'websocket'"), id="lifespan"),
            pytest.param("unknown", RuntimeError("Request scope type must be 'http' or 'websocket'"), id="unknown"),
        ],
        indirect=["exception"],
    )
    def test_init(self, scope_type, exception):
        with exception:
            HTTPConnection(types.Scope({"type": scope_type, "path": "/", "headers": []}))

    @pytest.mark.parametrize(
        ["key", "expected"],
        [
            pytest.param("method", "GET", id="method"),
            pytest.param("path", "/test", id="path"),
        ],
    )
    def test_getitem(self, conn, key, expected):
        assert conn[key] == expected

    def test_iter(self, conn, scope):
        assert set(scope.keys()).issubset(set(conn))

    def test_len(self, conn, scope):
        assert len(conn) == len(scope)

    def test_eq_is_identity(self, conn):
        assert conn == conn
        assert conn != HTTPConnection(conn.scope)

    def test_url(self, conn):
        url = conn.url

        assert isinstance(url, URL)
        assert str(url) == "https://example.com/test?foo=bar&baz=1"
        assert str(url.path) == "/test"

    def test_url_cached(self, conn):
        assert conn.url is conn.url

    def test_base_url(self, conn):
        assert str(conn.base_url) == "https://example.com/"

    def test_base_url_cached(self, conn):
        assert conn.base_url is conn.base_url

    def test_headers(self, conn):
        assert isinstance(conn.headers, Headers)
        assert conn.headers["content-type"] == "text/html"
        assert conn.headers["host"] == "example.com"

    def test_headers_cached(self, conn):
        assert conn.headers is conn.headers

    def test_query_params(self, conn):
        assert isinstance(conn.query_params, QueryParams)
        assert conn.query_params["foo"] == "bar"
        assert conn.query_params["baz"] == "1"

    def test_query_params_cached(self, conn):
        assert conn.query_params is conn.query_params

    @pytest.mark.parametrize(
        ["scope_extras", "expected"],
        [
            pytest.param({"path_params": {"id": "42"}}, {"id": "42"}, id="present"),
            pytest.param({}, {}, id="missing"),
        ],
    )
    def test_path_params(self, scope_extras, expected):
        scope = types.Scope({"type": "http", "path": "/", "headers": [], **scope_extras})
        conn = HTTPConnection(scope)

        assert conn.path_params == expected

    def test_cookies(self, conn):
        assert conn.cookies == {"session": "abc123", "theme": "dark"}

    def test_cookies_cached(self, conn):
        assert conn.cookies is conn.cookies

    def test_cookies_empty(self):
        conn = HTTPConnection(types.Scope({"type": "http", "path": "/", "headers": []}))

        assert conn.cookies == {}

    @pytest.mark.parametrize(
        ["scope_extras", "expected"],
        [
            pytest.param({"client": ("192.168.1.1", 12345)}, Address("192.168.1.1", 12345), id="present"),
            pytest.param({}, None, id="missing"),
        ],
    )
    def test_client(self, scope_extras, expected):
        scope = types.Scope({"type": "http", "path": "/", "headers": [], **scope_extras})
        conn = HTTPConnection(scope)

        assert conn.client == expected

    @pytest.mark.parametrize(
        ["scope_extras", "expected", "exception"],
        [
            pytest.param({"correlation_id": "foo-id-123"}, "foo-id-123", None, id="present"),
            pytest.param(
                {},
                None,
                ApplicationError("CorrelationIdMiddleware must be installed to access request.correlation_id"),
                id="missing",
            ),
        ],
        indirect=["exception"],
    )
    def test_correlation_id(self, scope_extras, expected, exception):
        conn = HTTPConnection(types.Scope({"type": "http", "path": "/", "headers": [], **scope_extras}))

        with exception:
            assert conn.correlation_id == expected

    @pytest.mark.parametrize(
        ["scope_extras", "expected", "exception"],
        [
            pytest.param({"session": {"user": "bob"}}, {"user": "bob"}, None, id="present"),
            pytest.param(
                {},
                None,
                ApplicationError("SessionMiddleware must be installed to access request.session"),
                id="missing",
            ),
        ],
        indirect=["exception"],
    )
    def test_session(self, scope_extras, expected, exception):
        conn = HTTPConnection(types.Scope({"type": "http", "path": "/", "headers": [], **scope_extras}))

        with exception:
            assert conn.session == expected

    @pytest.mark.parametrize(
        ["scope_extras", "expected", "exception"],
        [
            pytest.param({"auth": "token"}, "token", None, id="present"),
            pytest.param(
                {},
                None,
                ApplicationError("AuthenticationMiddleware must be installed to access request.auth"),
                id="missing",
            ),
        ],
        indirect=["exception"],
    )
    def test_auth(self, scope_extras, expected, exception):
        conn = HTTPConnection(types.Scope({"type": "http", "path": "/", "headers": [], **scope_extras}))

        with exception:
            assert conn.auth == expected

    @pytest.mark.parametrize(
        ["scope_extras", "expected", "exception"],
        [
            pytest.param({"user": {"name": "alice"}}, {"name": "alice"}, None, id="present"),
            pytest.param(
                {},
                None,
                ApplicationError("AuthenticationMiddleware must be installed to access request.user"),
                id="missing",
            ),
        ],
        indirect=["exception"],
    )
    def test_user(self, scope_extras, expected, exception):
        conn = HTTPConnection(types.Scope({"type": "http", "path": "/", "headers": [], **scope_extras}))

        with exception:
            assert conn.user == expected

    def test_app(self):
        app = object()
        scope = types.Scope({"type": "http", "path": "/", "headers": [], "app": app})
        conn = HTTPConnection(scope)

        assert conn.app is app

    def test_state(self, conn):
        assert isinstance(conn.state, State)
        conn.state.counter = 1

        assert conn.state.counter == 1
        assert conn.scope["state"]["counter"] == 1

    def test_state_replaces_plain_dict(self):
        scope = types.Scope({"type": "http", "path": "/", "headers": [], "state": {"existing": 1}})
        conn = HTTPConnection(scope)

        assert isinstance(conn.state, State)
        assert conn.state.existing == 1
        assert conn.scope["state"] is conn.state

    def test_state_preserves_existing_state(self):
        existing_state = State({"key": "value"})
        scope = types.Scope({"type": "http", "path": "/", "headers": [], "state": existing_state})
        conn = HTTPConnection(scope)

        assert conn.state is existing_state

    def test_state_cached(self, conn):
        assert conn.state is conn.state
