import functools
import inspect
import typing as t

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
    SessionMiddleware = None  # type: ignore[misc, assignment]

if t.TYPE_CHECKING:
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


class Middleware:
    def __init__(self, middleware: "types.Middleware", **kwargs: t.Any) -> None:
        self.middleware = middleware
        self.kwargs = kwargs

    def __call__(self, app: "types.App"):
        return self.middleware(app=app, **self.kwargs)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        middleware_name = (
            self.middleware.__name__ if inspect.isfunction(self.middleware) else self.middleware.__class__.__name__
        )
        args = ", ".join([middleware_name] + [f"{key}={value!r}" for key, value in self.kwargs.items()])
        return f"{name}({args})"


class MiddlewareStack:
    def __init__(self, app: "types.App", middleware: t.Sequence[Middleware], debug: bool):
        self.app = app
        self.middleware = list(reversed(middleware))
        self.debug = debug
        self._exception_handlers: t.Dict[
            t.Union[int, t.Type[Exception]], t.Callable[["Request", Exception], "Response"]
        ] = {}
        self._stack: t.Optional["types.App"] = None

    @property
    def stack(self) -> "types.App":
        if self._stack is None:
            self._stack = functools.reduce(
                lambda app, middleware: middleware(app=app),
                [
                    Middleware(ExceptionMiddleware, handlers=self._exception_handlers, debug=self.debug),
                    *self.middleware,
                    Middleware(ServerErrorMiddleware, debug=self.debug),
                ],
                self.app,
            )

        return self._stack

    @stack.deleter
    def stack(self):
        self._stack = None

    def add_exception_handler(
        self, key: t.Union[int, t.Type[Exception]], handler: t.Callable[["Request", Exception], "Response"]
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
        self.middleware.append(middleware)
        del self.stack

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        await self.stack(scope, receive, send)
