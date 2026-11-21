from flama import http, types
from flama.authentication import exceptions
from flama.errors.exception_handlers import ExceptionHandler
from flama.http.responses.api import APIErrorResponse

__all__ = ["AuthenticationExceptionHandler"]


class AuthenticationExceptionHandler(ExceptionHandler):
    """Answer an authentication error with a problem detail (RFC 9457) carrying its status.

    The response carries the error's ``WWW-Authenticate`` challenge, or its ``Retry-After`` when keys cannot be checked.
    """

    exc_class = exceptions.AuthenticationException

    def authentication_error(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.AuthenticationError
    ) -> http.Response:
        return APIErrorResponse(exc.detail, exc.status_code, headers=exc.headers)
