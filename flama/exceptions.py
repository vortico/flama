import http
import typing

import starlette.exceptions
import starlette.websockets

import flama.schemas.exceptions
from flama.schemas.exceptions import *  # noqa

__all__ = [
    "ComponentNotFound",
    "ConfigurationError",
    "DecodeError",
    "HTTPException",
    "NoReverseMatch",
    "NoCodecAvailable",
    "SerializationError",
    "ValidationError",
    "WebSocketException",
] + flama.schemas.exceptions.__all__


class DecodeError(Exception):
    """
    Raised by a Codec when `decode` fails due to malformed syntax.
    """

    def __init__(self, message, marker=None, base_format=None):
        Exception.__init__(self, message)
        self.message = message
        self.marker = marker
        self.base_format = base_format


class NoReverseMatch(Exception):
    """
    Raised by a Router when `reverse_url` is passed an invalid handler name.
    """

    ...


class NoCodecAvailable(Exception):
    ...


class ConfigurationError(Exception):
    ...


class WebSocketException(starlette.exceptions.WebSocketException):
    def __init__(self, code: int, reason: typing.Optional[str] = None) -> None:
        self.code = code
        self.reason = reason or ""

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(code={self.code!r}, reason={self.reason!r})"


class HTTPException(starlette.exceptions.HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: typing.Optional[typing.Union[str, typing.Dict[str, typing.List[str]]]] = None,
        headers: typing.Optional[dict] = None,
    ) -> None:
        if detail is None:
            detail = http.HTTPStatus(status_code).phrase
        self.status_code = status_code
        self.detail = detail  # type: ignore[assignment]
        self.headers = headers

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(status_code={self.status_code!r}, detail={self.detail!r})"


class ValidationError(HTTPException):
    def __init__(
        self,
        detail: typing.Optional[typing.Union[str, typing.Dict[str, typing.List[str]]]] = None,
        status_code: int = 400,
    ):
        super().__init__(status_code, detail=detail)


class SerializationError(HTTPException):
    def __init__(
        self, detail: typing.Union[None, str, typing.Dict[str, typing.List[str]]] = None, status_code: int = 500
    ):
        super().__init__(status_code, detail=detail)
