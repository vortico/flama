import dataclasses
import inspect
import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from flama import http
    from flama.applications import Flama
    from flama.routing import Route, WebSocketRoute


@dataclasses.dataclass(frozen=True)
class RequestParams:
    path: t.Dict[str, t.Any]
    query: t.Dict[str, t.Any]


@dataclasses.dataclass(frozen=True)
class RequestClient:
    host: str
    port: int


@dataclasses.dataclass(frozen=True)
class Request:
    path: str
    method: str
    params: RequestParams
    headers: t.Dict[str, str]
    cookies: t.Dict[str, str]
    client: t.Optional[RequestClient] = None

    @classmethod
    def from_request(cls, request: "http.Request") -> "Request":
        return cls(
            path=request.url.path,
            method=request.method,
            params=RequestParams(query=dict(request.query_params), path=dict(request.path_params)),
            headers=dict(request.headers),
            cookies=dict(request.cookies),
            client=RequestClient(host=request.client.host, port=request.client.port) if request.client else None,
        )


@dataclasses.dataclass(frozen=True)
class Frame:
    filename: str
    function: str
    line: int
    vendor: t.Optional[str]
    code: str

    @classmethod
    def from_frame_info(cls, frame: inspect.FrameInfo) -> "Frame":
        filename = Path(frame.filename).resolve()
        for sys_path in sys.path:
            try:
                relative_filename = filename.relative_to(sys_path)
                break
            except ValueError:  # pragma: no cover # Just a safety mechanism
                ...
        else:  # pragma: no cover # Just a safety mechanism
            raise ValueError(f"Filename '{filename}' not found in sys.path")

        try:
            vendor = str(filename.relative_to(sys.exec_prefix).parts[3])
        except ValueError:
            vendor = None

        with open(filename) as f:
            code = f.read()

        return cls(
            filename=str(relative_filename),
            function=frame.function,
            line=frame.lineno,
            vendor=vendor,
            code=code,
        )


@dataclasses.dataclass(frozen=True)
class Error:
    error: str
    description: str
    traceback: t.List[Frame]

    @classmethod
    def from_exception(cls, exc: Exception, context: int = 10) -> "Error":
        frames = inspect.getinnerframes(exc.__traceback__, context) if exc.__traceback__ else []
        exc_cls = exc if inspect.isclass(exc) else exc.__class__
        return cls(
            error=f"{exc_cls.__module__}.{exc_cls.__name__}" if exc_cls.__module__ != "builtins" else exc_cls.__name__,
            description=str(exc),
            traceback=[Frame.from_frame_info(frame=frame) for frame in frames],
        )


@dataclasses.dataclass(frozen=True)
class Environment:
    platform: str
    python: str
    python_version: str
    path: t.List[str]

    @classmethod
    def from_system(cls) -> "Environment":
        return cls(platform=sys.platform, python=sys.executable, python_version=sys.version, path=sys.path)


@dataclasses.dataclass(frozen=True)
class Endpoint:
    path: str
    endpoint: str
    module: t.Optional[str]
    file: str
    line: int
    name: t.Optional[str] = None

    @classmethod
    def from_route(cls, route: t.Union["Route", "WebSocketRoute"]) -> "Endpoint":
        handler = route.app.handler
        module = inspect.getmodule(route.app.handler)
        filename = Path(inspect.getfile(route.app.handler)).resolve()
        for sys_path in sys.path:
            try:
                relative_filename = filename.relative_to(sys_path)
                break
            except ValueError:  # pragma: no cover # Just a safety mechanism
                ...
        else:  # pragma: no cover # Just a safety mechanism
            raise ValueError(f"Filename '{filename}' not found in sys.path")

        return cls(
            path=str(route.path),
            endpoint=handler.__name__,
            module=module.__name__ if module else None,
            file=str(relative_filename),
            line=inspect.getsourcelines(route.app.handler)[1],
            name=route.name,
        )


@dataclasses.dataclass(frozen=True)
class App:
    urls: t.List[t.Union[Endpoint, "App"]]
    path: str
    name: t.Optional[str] = None

    @classmethod
    def from_app(cls, app: t.Any, path: str = "/", name: t.Optional[str] = None) -> "App":
        urls: t.List[t.Union[Endpoint, "App"]] = []
        for route in app.routes:
            try:
                urls.append(App.from_app(route.app, path=route.path.path, name=route.name))
            except AttributeError:
                urls.append(Endpoint.from_route(route))

        return cls(urls=urls, path=path, name=name)


@dataclasses.dataclass(frozen=True)
class ErrorContext:
    request: Request
    environment: Environment
    error: Error

    @classmethod
    def build(cls, request: "http.Request", exc: Exception) -> "ErrorContext":
        return cls(
            request=Request.from_request(request),
            environment=Environment.from_system(),
            error=Error.from_exception(exc),
        )


@dataclasses.dataclass(frozen=True)
class NotFoundContext:
    request: Request
    environment: Environment
    app: App

    @classmethod
    def build(cls, request: "http.Request", app: "Flama") -> "NotFoundContext":
        return cls(request=Request.from_request(request), environment=Environment.from_system(), app=App.from_app(app))
