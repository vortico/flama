__all__ = ["RepositoryException", "IntegrityError", "NotFoundError"]


class RepositoryException(Exception):
    ...


class IntegrityError(RepositoryException):
    ...


class NotFoundError(RepositoryException):
    ...
