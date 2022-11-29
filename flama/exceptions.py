import http
import typing as t

import starlette.exceptions

import flama.schemas.exceptions

__all__ = [
    "DecodeError",
    "HTTPException",
    "NoCodecAvailable",
    "SerializationError",
    "ValidationError",
    "WebSocketException",
    "NotFoundException",
    "MethodNotAllowedException",
]

__all__ += flama.schemas.exceptions.__all__


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
        detail: t.Optional[t.Union[str, t.Dict[str, t.List[str]]]] = None,
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
        detail: t.Optional[t.Union[str, t.Dict[str, t.List[str]]]] = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(status_code, detail=detail)


class SerializationError(HTTPException):
    def __init__(self, detail: t.Union[None, str, t.Dict[str, t.List[str]]] = None, status_code: int = 500) -> None:
        super().__init__(status_code, detail=detail)


class NotFoundException(Exception):
    def __init__(
        self, path: t.Optional[str] = None, params: t.Optional[t.Dict[str, t.Any]] = None, name: t.Optional[str] = None
    ) -> None:
        self.path = path
        self.params = params
        self.name = name

    def __str__(self) -> str:
        params = ("path", "params", "name")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"


class MethodNotAllowedException(Exception):
    def __init__(
        self, path: str, method: str, allowed: t.Set[str], params: t.Optional[t.Dict[str, t.Any]] = None
    ) -> None:
        self.path = path
        self.params = params
        self.method = method
        self.allowed = allowed

    def __str__(self) -> str:
        params = ("path", "params", "method", "allowed")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"
