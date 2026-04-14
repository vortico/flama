import typing as t
from collections.abc import Iterator, Mapping

from flama import types
from flama._core.cookies import parse_cookie_header
from flama.exceptions import ApplicationError
from flama.http.data_structures import Address, Headers, QueryParams, State
from flama.url import URL

__all__ = ["HTTPConnection"]


class HTTPConnection(Mapping[str, t.Any]):
    """Base class for incoming HTTP connections.

    Provides the properties common to both :class:`Request` and ``WebSocket``.

    :param scope: ASGI connection scope.
    """

    def __init__(self, scope: types.Scope, receive: types.Receive | None = None) -> None:
        if scope["type"] not in ("http", "websocket"):
            raise RuntimeError("Request scope type must be 'http' or 'websocket'")

        self.scope = scope

    def __getitem__(self, key: str) -> t.Any:
        return self.scope[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.scope)

    def __len__(self) -> int:
        return len(self.scope)

    __eq__ = object.__eq__
    __hash__ = object.__hash__

    @property
    def app(self) -> t.Any:
        return self.scope["app"]

    @property
    def url(self) -> URL:
        if not hasattr(self, "_url"):
            self._url = URL.from_scope(self.scope)
        return self._url

    @property
    def base_url(self) -> URL:
        if not hasattr(self, "_base_url"):
            scope = dict(self.scope)
            app_root_path = scope.get("app_root_path", scope.get("root_path", ""))
            scope["path"] = app_root_path if app_root_path.endswith("/") else app_root_path + "/"
            scope["query_string"] = b""
            scope["root_path"] = app_root_path
            self._base_url = URL.from_scope(scope)
        return self._base_url

    @property
    def headers(self) -> Headers:
        if not hasattr(self, "_headers"):
            self._headers = Headers(scope=self.scope)
        return self._headers

    @property
    def query_params(self) -> QueryParams:
        if not hasattr(self, "_query_params"):
            self._query_params = QueryParams(self.scope.get("query_string", b""))
        return self._query_params

    @property
    def path_params(self) -> dict[str, t.Any]:
        return self.scope.get("path_params", {})

    @property
    def cookies(self) -> dict[str, str]:
        if not hasattr(self, "_cookies"):
            self._cookies: dict[str, str] = dict(parse_cookie_header(self.headers.get("cookie", "")))
        return self._cookies

    @property
    def client(self) -> Address | None:
        if (host_port := self.scope.get("client")) is not None:
            return Address(*host_port)
        return None

    @property
    def correlation_id(self) -> str:
        try:
            return self.scope["correlation_id"]
        except KeyError:
            raise ApplicationError("CorrelationIdMiddleware must be installed to access request.correlation_id")

    @property
    def session(self) -> dict[str, t.Any]:
        try:
            return self.scope["session"]
        except KeyError:
            raise ApplicationError("SessionMiddleware must be installed to access request.session")

    @property
    def auth(self) -> t.Any:
        try:
            return self.scope["auth"]
        except KeyError:
            raise ApplicationError("AuthenticationMiddleware must be installed to access request.auth")

    @property
    def user(self) -> t.Any:
        try:
            return self.scope["user"]
        except KeyError:
            raise ApplicationError("AuthenticationMiddleware must be installed to access request.user")

    @property
    def state(self) -> State:
        if not hasattr(self, "_state"):
            scope_state = self.scope.get("state")
            if isinstance(scope_state, State):
                self._state = scope_state
            else:
                self._state = State(scope_state)
                self.scope["state"] = self._state
        return self._state
