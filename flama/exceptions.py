import http
import typing as t

import starlette.exceptions

from flama import compat

__all__ = [
    "ApplicationError",
    "DependencyNotInstalled",
    "SQLAlchemyError",
    "DecodeError",
    "HTTPException",
    "NoCodecAvailable",
    "SerializationError",
    "ValidationError",
    "WebSocketException",
    "NotFoundException",
    "MethodNotAllowedException",
    "FrameworkNotInstalled",
    "FrameworkVersionWarning",
]


class ApplicationError(Exception):
    ...


class DependencyNotInstalled(ApplicationError):
    class Dependency(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
        pydantic = "pydantic"
        marshmallow = "marshmallow"
        apispec = "apispec"
        typesystem = "typesystem"
        sqlalchemy = "sqlalchemy[asyncio]"
        httpx = "httpx"
        tomli = "tomli"

    def __init__(
        self,
        *,
        dependency: t.Optional[t.Union[str, Dependency]] = None,
        dependant: t.Optional[str] = None,
        msg: str = "",
    ) -> None:
        super().__init__()
        self.dependency = self.Dependency(dependency) if dependency else None
        self.dependant = dependant
        self.msg = msg

    def __str__(self) -> str:
        if self.dependency:
            s = f"Dependency '{self.dependency.value}' must be installed"
            if self.dependant:
                s += f" to use '{self.dependant}'"
            if self.msg:
                s += f" ({self.msg})"
        else:
            s = self.msg

        return s

    def __repr__(self) -> str:
        params = ("msg", "dependency", "dependant")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"


class SQLAlchemyError(ApplicationError):
    ...


class DecodeError(Exception):
    """
    Raised by a Codec when `decode` fails due to malformed syntax.
    """

    def __init__(self, message, marker=None, base_format=None) -> None:
        super().__init__(self, message)
        self.message = message
        self.marker = marker
        self.base_format = base_format


class NoCodecAvailable(Exception):
    ...


class WebSocketException(starlette.exceptions.WebSocketException):
    def __init__(self, code: int, reason: t.Optional[str] = None) -> None:
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


class HTTPException(starlette.exceptions.HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: t.Optional[t.Union[str, dict[str, t.Any]]] = None,
        headers: t.Optional[dict] = None,
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
        detail: t.Optional[t.Union[str, dict[str, list[str]]]] = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(status_code, detail=detail)


class SerializationError(HTTPException):
    def __init__(self, detail: t.Union[None, str, dict[str, list[str]]] = None, status_code: int = 500) -> None:
        super().__init__(status_code, detail=detail)


class NotFoundException(Exception):
    def __init__(
        self, path: t.Optional[str] = None, params: t.Optional[dict[str, t.Any]] = None, name: t.Optional[str] = None
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


class MethodNotAllowedException(Exception):
    def __init__(self, path: str, method: str, allowed: set[str], params: t.Optional[dict[str, t.Any]] = None) -> None:
        self.path = path
        self.params = params
        self.method = method
        self.allowed = allowed

    def __str__(self) -> str:
        params = ("path", "params", "method", "allowed")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"Method not allowed ({formatted_params})"

    def __repr__(self) -> str:
        params = ("path", "params", "method", "allowed")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"


class FrameworkNotInstalled(Exception):
    """Cannot find an installed version of the framework."""

    ...


class FrameworkVersionWarning(Warning):
    """Warning for when a framework version does not match."""

    ...
