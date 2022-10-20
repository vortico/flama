import typing

from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from flama.debug.middleware import ExceptionMiddleware, ServerErrorMiddleware

try:
    from starlette.middleware.sessions import SessionMiddleware
except Exception:
    SessionMiddleware = None  # type: ignore

if typing.TYPE_CHECKING:
    from flama import types
    from flama.http import Request, Response

__all__ = [
    "AuthenticationMiddleware",
    "BaseHTTPMiddleware",
    "CORSMiddleware",
    "ExceptionMiddleware",
    "GZipMiddleware",
    "HTTPSRedirectMiddleware",
    "Middleware",
    "MiddlewareStack",
    "SessionMiddleware",
    "TrustedHostMiddleware",
]


class MiddlewareStack:
    def __init__(self, app: "types.App", middleware: typing.Sequence[Middleware], debug: bool):
        self.app = app
        self.middleware = list(middleware)
        self.debug = debug
        self._exception_handlers: typing.Dict[
            typing.Union[int, typing.Type[Exception]], typing.Callable[["Request", Exception], "Response"]
        ] = {}
        self._stack: typing.Optional["types.App"] = None

    @property
    def stack(self) -> "types.App":
        if self._stack is None:
            app = self.app
            for cls, options in reversed(
                [
                    Middleware(ServerErrorMiddleware, debug=self.debug),
                    *self.middleware,
                    Middleware(ExceptionMiddleware, handlers=self._exception_handlers, debug=self.debug),
                ]
            ):
                app = cls(app=app, **options)
            self._stack = app

        return self._stack

    @stack.deleter
    def stack(self):
        self._stack = None

    def add_exception_handler(
        self,
        key: typing.Union[int, typing.Type[Exception]],
        handler: typing.Callable[["Request", Exception], "Response"],
    ):
        """Adds a new handler for an exception type or a HTTP status code.

        :param key: Exception type or HTTP status code.
        :param handler: Exception handler.
        """
        self._exception_handlers[key] = handler
        del self.stack

    def add_middleware(self, middleware: Middleware):
        """Adds a new middleware to the stack.

        :param middleware: Middleware.
        """
        self.middleware.insert(0, middleware)
        del self.stack

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        await self.stack(scope, receive, send)
