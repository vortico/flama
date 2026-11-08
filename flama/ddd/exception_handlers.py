from flama import http, types
from flama.ddd import exceptions
from flama.errors.exception_handlers import ExceptionHandler
from flama.http.responses.api import APIErrorResponse

__all__ = ["RepositoryExceptionHandler"]


class RepositoryExceptionHandler(ExceptionHandler):
    """Answer the repository errors a client can act on, leaving any other to the server-error handling.

    The message names the resource only, never the storage error the repository error was raised from.
    """

    exc_class = exceptions.RepositoryException

    def not_found(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.NotFoundError
    ) -> http.Response:
        return APIErrorResponse(detail=str(exc), status_code=404, exception=exc)

    def already_exists(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.AlreadyExistsError
    ) -> http.Response:
        return APIErrorResponse(detail=str(exc), status_code=409, exception=exc)

    def integrity(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.IntegrityError
    ) -> http.Response:
        return APIErrorResponse(detail=str(exc), status_code=400, exception=exc)
