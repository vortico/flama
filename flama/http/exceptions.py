import http
import typing as t

if t.TYPE_CHECKING:
    from flama.types import ErrorDetail

__all__ = ["HTTPException", "ValidationError", "SerializationError"]


class HTTPException(Exception):
    """An HTTP error, answered as a problem detail (RFC 9457).

    :param status_code: HTTP status code.
    :param detail: Human-readable explanation of this occurrence, the status phrase by default.
    :param headers: Headers of the response.
    :param type: URI reference identifying the problem type, ``about:blank`` when the status says everything.
    :param title: Short summary of the problem type, the status phrase by default.
    :param instance: URI reference identifying this occurrence, if it can be told apart from others.
    :param errors: Errors located by a JSON Pointer into the value they were raised for.
    :param extensions: Extension members of the problem.
    :raises TypeError: If the detail is not a string.
    :raises ValueError: If an extension member is named after a member of the problem.
    """

    MEMBERS: t.ClassVar[frozenset[str]] = frozenset({"type", "title", "status", "detail", "instance", "errors"})

    def __init__(
        self,
        status_code: int,
        detail: str | None = None,
        headers: t.Mapping[str, str] | None = None,
        *,
        type: str = "about:blank",
        title: str | None = None,
        instance: str | None = None,
        errors: "t.Sequence[ErrorDetail]" = (),
        extensions: t.Mapping[str, t.Any] | None = None,
    ) -> None:
        if detail is not None and not isinstance(detail, str):
            raise TypeError(
                "The detail of an HTTP exception is a string, give errors as 'errors' and data as 'extensions'"
            )

        if reserved := self.MEMBERS & set(extensions or {}):
            raise ValueError(f"Extension members cannot be named after members of the problem: {sorted(reserved)}")

        self.status_code = status_code
        self.detail = detail if detail is not None else http.HTTPStatus(status_code).phrase
        self.headers = dict(headers) if headers is not None else None
        self.type = type
        self.title = title if title is not None else http.HTTPStatus(status_code).phrase
        self.instance = instance
        self.errors = list(errors)
        self.extensions = dict(extensions or {})

    def __str__(self) -> str:
        return "\n".join(
            [
                self.detail,
                *(f"{x.pointer.removeprefix('#/')}: {x.detail}" if x.pointer != "#" else x.detail for x in self.errors),
            ]
        )

    def __repr__(self) -> str:
        params = ("status_code", "detail", "headers", "instance", "errors", "extensions")
        formatted_params = ", ".join([f"{x}={getattr(self, x)}" for x in params if getattr(self, x)])
        return f"{self.__class__.__name__}({formatted_params})"

    def __eq__(self, other):
        return (
            isinstance(other, HTTPException)
            and self.status_code == other.status_code
            and self.detail == other.detail
            and self.headers == other.headers
            and self.type == other.type
            and self.title == other.title
            and self.instance == other.instance
            and self.errors == other.errors
            and self.extensions == other.extensions
        )


class ValidationError(HTTPException):
    """A request that is not valid, with the errors found in it.

    :param detail: Human-readable explanation.
    :param errors: Errors located by a JSON Pointer into the request's values.
    :param status_code: HTTP status code.
    """

    def __init__(
        self, detail: str | None = None, *, errors: "t.Sequence[ErrorDetail]" = (), status_code: int = 400
    ) -> None:
        super().__init__(status_code, detail=detail or "The request is not valid", errors=errors)


class SerializationError(HTTPException):
    """A response that cannot be serialised, with the errors found in it.

    :param detail: Human-readable explanation.
    :param errors: Errors located by a JSON Pointer into the response's content.
    :param status_code: HTTP status code.
    """

    def __init__(
        self, detail: str | None = None, *, errors: "t.Sequence[ErrorDetail]" = (), status_code: int = 500
    ) -> None:
        super().__init__(status_code, detail=detail or "The response cannot be serialised", errors=errors)
