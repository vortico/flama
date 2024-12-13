import typing as t

__all__ = [
    "Empty",
    "RepositoryException",
    "IntegrityError",
    "NotFoundError",
    "AlreadyExistsError",
    "MultipleRecordsError",
]


class Empty(Exception):
    ...


class RepositoryException(Exception):
    ...


class ResourceException(RepositoryException):
    _error_message: t.ClassVar[str] = "exception"

    def __init__(self, *, resource: str, id: t.Any = None, detail: str = "") -> None:
        super().__init__()
        self.resource = resource
        self.id = id
        self.detail = detail

    def __str__(self) -> str:
        return (
            f"Resource '{self.resource}'"
            + (f" ({self.id})" if self.id else "")
            + f" {self._error_message}"
            + (f" ({self.detail})" if self.detail else "")
        )

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}("{self.__str__()}")'


class IntegrityError(ResourceException):
    _error_message = "integrity failed"


class NotFoundError(ResourceException):
    _error_message = "not found"


class AlreadyExistsError(ResourceException):
    _error_message = "already exists"


class MultipleRecordsError(ResourceException):
    _error_message = "multiple records found"
