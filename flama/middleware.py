import functools
import typing as t

import starlette.middleware.authentication
import starlette.middleware.base
import starlette.middleware.cors
import starlette.middleware.gzip
import starlette.middleware.httpsredirect
import starlette.middleware.trustedhost

from flama import concurrency
from flama.debug.middleware import ExceptionMiddleware, ServerErrorMiddleware

if t.TYPE_CHECKING:
    from flama import Flama, types
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

try:
    import starlette.middleware.sessions

    class SessionMiddleware(starlette.middleware.sessions.SessionMiddleware):
        def __init__(self, app: "types.App", *args, **kwargs):
            super().__init__(app, *args, **kwargs)  # type: ignore[arg-type]

        async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:  # type: ignore[overrid]
            return await super().__call__(scope, receive, send)  # type: ignore[assignment]

except ModuleNotFoundError:
    SessionMiddleware = None  # type: ignore[assignment]


class AuthenticationMiddleware(starlette.middleware.authentication.AuthenticationMiddleware):
    def __init__(self, app: "types.App", *args, **kwargs):
        super().__init__(app, *args, **kwargs)  # type: ignore[arg-type]

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:  # type: ignore[overrid]
        return await super().__call__(scope, receive, send)  # type: ignore[assignment]


class BaseHTTPMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    def __init__(self, app: "types.App", *args, **kwargs):
        super().__init__(app, *args, **kwargs)  # type: ignore[arg-type]

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:  # type: ignore[overrid]
        return await super().__call__(scope, receive, send)  # type: ignore[assignment]


class CORSMiddleware(starlette.middleware.cors.CORSMiddleware):
    def __init__(self, app: "types.App", *args, **kwargs):
        super().__init__(app, *args, **kwargs)  # type: ignore[arg-type]

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:  # type: ignore[overrid]
        return await super().__call__(scope, receive, send)  # type: ignore[assignment]


class GZipMiddleware(starlette.middleware.gzip.GZipMiddleware):
    def __init__(self, app: "types.App", *args, **kwargs):
        super().__init__(app, *args, **kwargs)  # type: ignore[arg-type]

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:  # type: ignore[overrid]
        return await super().__call__(scope, receive, send)  # type: ignore[assignment]


class HTTPSRedirectMiddleware(starlette.middleware.httpsredirect.HTTPSRedirectMiddleware):
    def __init__(self, app: "types.App", *args, **kwargs):
        super().__init__(app, *args, **kwargs)  # type: ignore[arg-type]

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:  # type: ignore[overrid]
        return await super().__call__(scope, receive, send)  # type: ignore[assignment]


class TrustedHostMiddleware(starlette.middleware.trustedhost.TrustedHostMiddleware):
    def __init__(self, app: "types.App", *args, **kwargs):
        super().__init__(app, *args, **kwargs)  # type: ignore[arg-type]

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:  # type: ignore[overrid]
        return await super().__call__(scope, receive, send)  # type: ignore[assignment]


class Middleware:
    def __init__(self, middleware: "types.Middleware", **kwargs: t.Any) -> None:
        self.middleware = middleware
        self.kwargs = kwargs

    def __call__(self, app: "types.App") -> t.Union["types.MiddlewareClass", "types.App"]:
        return self.middleware(app, **self.kwargs)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        middleware_name = (
            self.middleware.__class__.__name__
            if isinstance(self.middleware, types.MiddlewareClass)
            else self.middleware.__name__
        )
        args = ", ".join([middleware_name] + [f"{key}={value!r}" for key, value in self.kwargs.items()])
        return f"{name}({args})"


class MiddlewareStack:
    def __init__(self, app: "Flama", middleware: t.Sequence[Middleware], debug: bool):
        self.app = app
        self.middleware = list(reversed(middleware))
        self.debug = debug
        self._exception_handlers: dict[
            t.Union[int, type[Exception]], t.Callable[["Request", Exception], "Response"]
        ] = {}
        self._stack: t.Optional[t.Union["types.MiddlewareClass", "types.App"]] = None

    @property
    def stack(
        self,
    ) -> t.Union["types.MiddlewareClass", "types.App"]:
        if self._stack is None:
            self._stack = functools.reduce(
                lambda app, middleware: middleware(app=app),
                [
                    Middleware(ExceptionMiddleware, handlers=self._exception_handlers, debug=self.debug),
                    *self.middleware,
                    Middleware(ServerErrorMiddleware, debug=self.debug),
                ],
                self.app.router,
            )

        return self._stack

    @stack.deleter
    def stack(self):
        self._stack = None

    def add_exception_handler(
        self, key: t.Union[int, type[Exception]], handler: t.Callable[["Request", Exception], "Response"]
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
        await concurrency.run(self.stack, scope, receive, send)
