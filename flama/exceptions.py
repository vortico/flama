import http
import typing as t

from flama import _imports

__all__ = [
    "ApplicationError",
    "DependencyNotInstalled",
    "SQLAlchemyError",
    "DecodeError",
    "HTTPException",
    "JSONRPCException",
    "NoCodecAvailable",
    "SerializationError",
    "ValidationError",
    "WebSocketException",
    "RoutingException",
    "NotFoundException",
    "MethodNotAllowedException",
    "FrameworkVersionWarning",
]


class ApplicationError(Exception): ...


class DependencyNotInstalled(ApplicationError):
    """Cannot find an installed version of a dependency.

    :param dependencies: Dependencies any of which would satisfy the requirement.
    :param msg: Detail on what needs them.
    """

    def __init__(self, *dependencies: "_imports.DependencyPackage | _imports.DependencyName", msg: str = "") -> None:
        self.dependencies = tuple(_imports.DependencyPackage(dependency) for dependency in dependencies)
        self.msg = msg
        super().__init__(*self.dependencies)

    def __str__(self) -> str:
        if not self.dependencies:
            return self.msg

        packages = " or ".join(f"'{dependency.package}'" for dependency in self.dependencies)
        detail = f" ({self.msg})" if self.msg else ""
        install = _imports.DependencyPackage.install(*self.dependencies)
        return f"Dependency {packages} must be installed{detail} ({install})"

    def __repr__(self) -> str:
        params = ", ".join([*(repr(str(d)) for d in self.dependencies), *([f"msg={self.msg!r}"] if self.msg else [])])
        return f"{self.__class__.__name__}({params})"


class SQLAlchemyError(ApplicationError): ...


class DecodeError(Exception):
    """
    Raised by a Codec when `decode` fails due to malformed syntax.
    """

    def __init__(self, message, marker=None, base_format=None) -> None:
        super().__init__(self, message)
        self.message = message
        self.marker = marker
        self.base_format = base_format


class NoCodecAvailable(RuntimeError): ...


class WebSocketException(Exception):
    def __init__(self, code: int, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason or ""

    def __str__(self) -> str:
        return str(self.reason)

    def __repr__(self) -> str:
        params = ("code", "reason")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"

    def __eq__(self, other):
        return isinstance(other, WebSocketException) and self.code == other.code and self.reason == other.reason


class WebSocketDisconnect(WebSocketException):
    """Raised when a WebSocket client disconnects."""

    def __init__(self, code: int = 1000, reason: str | None = None) -> None:
        super().__init__(code, reason)


class HTTPException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str | dict[str, t.Any] | None = None,
        headers: dict | None = None,
    ) -> None:
        if detail is None:
            detail = http.HTTPStatus(status_code).phrase
        self.status_code = status_code
        self.detail = detail  # type: ignore[assignment]
        self.headers = headers

    def __str__(self) -> str:
        return str(self.detail)

    def __repr__(self) -> str:
        params = ("status_code", "detail", "headers")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"

    def __eq__(self, other):
        return (
            isinstance(other, HTTPException)
            and self.status_code == other.status_code
            and self.detail == other.detail
            and self.headers == other.headers
        )


class ValidationError(HTTPException):
    def __init__(
        self,
        detail: str | dict[str, list[str]] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(status_code, detail=detail)


class SerializationError(HTTPException):
    def __init__(self, detail: None | str | dict[str, list[str]] = None, status_code: int = 500) -> None:
        super().__init__(status_code, detail=detail)


class RoutingException(Exception):
    """Base exception for a request that cannot be routed to an endpoint."""


class NotFoundException(RoutingException):
    def __init__(
        self, path: str | None = None, params: dict[str, t.Any] | None = None, name: str | None = None
    ) -> None:
        self.path = path
        self.params = params
        self.name = name

    def __str__(self) -> str:
        params = ("path", "params", "name")
        formatted_params = ", ".join([f"{x}={repr(getattr(self, x))}" for x in params if getattr(self, x)])
        return f"Path not found ({formatted_params})"

    def __repr__(self) -> str:
        params = ("path", "params", "name")
        formatted_params = ", ".join([f"{x}={repr(getattr(self, x))}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"


class MethodNotAllowedException(RoutingException):
    def __init__(self, path: str, method: str, allowed: set[str]) -> None:
        self.path = path
        self.method = method
        self.allowed = allowed

    def __str__(self) -> str:
        params = ("path", "method", "allowed")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"Method not allowed ({formatted_params})"

    def __repr__(self) -> str:
        params = ("path", "method", "allowed")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"


class JSONRPCException(Exception):
    """Base exception for JSON-RPC protocol errors."""

    def __init__(
        self, status_code: int, detail: str | None = None, request_id: t.Any = None, data: t.Any = None
    ) -> None:
        from flama.http import JSONRPCStatus

        super().__init__()
        self.status_code = status_code
        self.detail = detail if detail is not None else JSONRPCStatus(status_code).phrase
        self.request_id = request_id
        self.data = data

    def __str__(self) -> str:
        return str(self.detail)

    def __repr__(self) -> str:
        params = ("status_code", "detail")
        formatted_params = ", ".join([f"{x}={getattr(self, x)!r}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, JSONRPCException)
            and self.status_code == other.status_code
            and self.detail == other.detail
        )


class FrameworkVersionWarning(Warning):
    """Warning for when a framework version does not match."""

    ...
