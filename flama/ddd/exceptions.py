__all__ = ["RepositoryException", "IntegrityError", "NotFoundError", "MultipleRecordsError"]


class RepositoryException(Exception):
    ...


class IntegrityError(RepositoryException):
    ...


class NotFoundError(RepositoryException):
    ...


class MultipleRecordsError(RepositoryException):
    ...
