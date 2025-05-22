import dataclasses
import datetime
import logging
import typing as t
from http.cookies import SimpleCookie

from flama import Flama, types
from flama.authentication.types import AccessToken, RefreshToken
from flama.exceptions import HTTPException
from flama.http import Request as HTTPRequest

logger = logging.getLogger(__name__)

__all__ = ["Endpoint", "Authentication", "Request", "Response", "Error", "TelemetryData"]


@dataclasses.dataclass
class Endpoint:
    path: str
    name: t.Optional[str]
    tags: dict[str, t.Any]

    @classmethod
    async def from_scope(cls, *, scope: types.Scope, receive: types.Receive, send: types.Send) -> "Endpoint":
        app: Flama = scope["app"]
        route, _ = app.router.resolve_route(scope)

        return cls(path=str(route.path), name=route.name, tags=route.tags)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "path": self.path,
            "name": self.name,
            "tags": self.tags,
        }


@dataclasses.dataclass
class Authentication:
    access: t.Optional[AccessToken]
    refresh: t.Optional[RefreshToken]

    @classmethod
    async def from_scope(cls, *, scope: types.Scope, receive: types.Receive, send: types.Send) -> "Authentication":
        app: Flama = scope["app"]
        context = {"scope": scope, "request": HTTPRequest(scope, receive=receive)}

        try:
            access = await app.injector.value(AccessToken, context)
        except Exception:
            access = None

        try:
            refresh = await app.injector.value(RefreshToken, context)
        except Exception:
            refresh = None

        return cls(access=access, refresh=refresh)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "access": self.access.to_dict() if self.access else None,
            "refresh": self.refresh.to_dict() if self.refresh else None,
        }


@dataclasses.dataclass
class Request:
    headers: dict[str, t.Any]
    cookies: dict[str, t.Any]
    query_parameters: dict[str, t.Any]
    path_parameters: dict[str, t.Any]
    body: bytes = b""
    timestamp: datetime.datetime = dataclasses.field(
        init=False, default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    @classmethod
    async def from_scope(cls, *, scope: types.Scope, receive: types.Receive, send: types.Send) -> "Request":
        app: Flama = scope["app"]
        context = {"scope": scope, "request": HTTPRequest(scope, receive=receive), "route": app.resolve_route(scope)[0]}

        headers = dict(await app.injector.value(types.Headers, context))
        cookies = dict(await app.injector.value(types.Cookies, context))
        query = dict(await app.injector.value(types.QueryParams, context))
        path = dict(await app.injector.value(types.PathParams, context))

        return cls(headers=headers, cookies=cookies, query_parameters=query, path_parameters=path)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "headers": self.headers,
            "cookies": self.cookies,
            "query_parameters": self.query_parameters,
            "path_parameters": self.path_parameters,
            "body": self.body,
        }


@dataclasses.dataclass
class Response:
    headers: t.Optional[dict[str, t.Any]]
    cookies: t.Optional[dict[str, t.Any]] = dataclasses.field(init=False)
    body: bytes = b""
    status_code: t.Optional[int] = None
    timestamp: datetime.datetime = dataclasses.field(
        init=False, default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def __post_init__(self):
        if self.headers:
            cookie = SimpleCookie()
            cookie.load(self.headers.get("cookie", ""))
        else:
            cookie = {}

        self.cookies = {
            str(name): {**{str(k): str(v) for k, v in morsel.items()}, "value": morsel.value}
            for name, morsel in cookie.items()
        }

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "headers": self.headers,
            "cookies": self.cookies,
            "body": self.body,
            "status_code": self.status_code,
        }


@dataclasses.dataclass
class Error:
    detail: str
    status_code: t.Optional[int] = None
    timestamp: datetime.datetime = dataclasses.field(
        init=False, default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    @classmethod
    async def from_exception(cls, *, exception: Exception) -> "Error":
        if isinstance(exception, HTTPException):
            return cls(status_code=exception.status_code, detail=str(exception.detail))

        return cls(detail=str(exception))

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "detail": self.detail,
            "status_code": self.status_code,
        }


@dataclasses.dataclass
class TelemetryData:
    type: t.Literal["http", "websocket"]
    endpoint: Endpoint
    authentication: Authentication
    request: Request
    response: t.Optional[Response] = None
    error: t.Optional[Error] = None
    extra: dict[t.Any, t.Any] = dataclasses.field(default_factory=dict)

    @classmethod
    async def from_scope(cls, *, scope: types.Scope, receive: types.Receive, send: types.Send) -> "TelemetryData":
        return cls(
            type=scope["type"],
            endpoint=await Endpoint.from_scope(scope=scope, receive=receive, send=send),
            authentication=await Authentication.from_scope(scope=scope, receive=receive, send=send),
            request=await Request.from_scope(scope=scope, receive=receive, send=send),
        )

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "type": self.type,
            "endpoint": self.endpoint.to_dict(),
            "authentication": self.authentication.to_dict(),
            "request": self.request.to_dict(),
            "response": self.response.to_dict() if self.response else None,
            "error": self.error.to_dict() if self.error else None,
            "extra": self.extra,
        }
