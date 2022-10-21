import dataclasses
import inspect
import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from flama import http


@dataclasses.dataclass
class RequestParams:
    path: t.Dict[str, t.Any]
    query: t.Dict[str, t.Any]


@dataclasses.dataclass
class RequestClient:
    host: str
    port: int


@dataclasses.dataclass
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


@dataclasses.dataclass
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
            except ValueError:
                ...
        else:
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


@dataclasses.dataclass
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


@dataclasses.dataclass
class Environment:
    platform: str
    python: str
    python_version: str
    path: t.List[str]

    @classmethod
    def from_system(cls) -> "Environment":
        return cls(platform=sys.platform, python=sys.executable, python_version=sys.version, path=sys.path)


@dataclasses.dataclass
class ErrorContext:
    request: Request
    error: Error
    environment: Environment

    @classmethod
    def build(cls, request: "http.Request", exc: Exception) -> "ErrorContext":
        return cls(
            request=Request.from_request(request),
            error=Error.from_exception(exc),
            environment=Environment.from_system(),
        )
