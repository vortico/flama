import typing as t

from flama import concurrency, types
from flama.debug.types import ExceptionHandler

__all__ = ["Middleware", "MiddlewareStack"]


class _BaseMiddleware:
    app: types.ASGIApp

    def _build(self, app: types.ASGIApp) -> "_BaseMiddleware":
        """Inject the downstream ASGI application.

        :param app: The downstream ASGI application.
        :return: This middleware instance.
        """
        self.app = app
        return self

    async def on_startup(self) -> None: ...

    async def on_shutdown(self) -> None: ...


class Middleware(_BaseMiddleware):
    """Base class for all Flama middleware.

    Subclass this to create custom middleware. The downstream ``app`` is injected
    by :class:`MiddlewareStack` via :meth:`_build` -- it must **not** be passed
    in ``__init__``.

    Override :meth:`on_startup` and :meth:`on_shutdown` for lifecycle hooks, and
    implement :meth:`__call__` for the ASGI interface.
    """

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await concurrency.run(self.app, scope, receive, send)


class MiddlewareStack:
    """Ordered middleware chain with lifecycle management.

    Builds an ASGI pipeline by wrapping the application router with each
    middleware in order, bookended by :class:`ExceptionMiddleware` (innermost)
    and :class:`ServerErrorMiddleware` (outermost).

    :param app: The Flama application.
    :param middleware: Sequence of :class:`Middleware` instances.
    :param debug: Whether to enable debug mode on error middleware.
    """

    def __init__(self, app: "types.App", middleware: t.Sequence[Middleware], debug: bool) -> None:
        self.app = app
        self.middleware = list(reversed(middleware))
        self.debug = debug
        self._exception_handlers: dict[int | type[Exception], ExceptionHandler] = {}
        self._stack: types.ASGIApp | None = None
        self._instances: list[t.Any] = []

    @property
    def stack(self) -> "types.ASGIApp":
        if self._stack is None:
            from flama.debug.middleware import ExceptionMiddleware, ServerErrorMiddleware

            self._instances.clear()
            inner_middleware = [
                ExceptionMiddleware(handlers=self._exception_handlers, debug=self.debug),
                *self.middleware,
                ServerErrorMiddleware(debug=self.debug),
            ]
            app: types.ASGIApp = self.app.router
            for m in inner_middleware:
                m._build(app)
                self._instances.append(m)
                app = t.cast(types.ASGIApp, m)

            self._stack = app

        return self._stack

    @stack.deleter
    def stack(self):
        self._stack = None
        self._instances.clear()

    async def on_startup(self) -> None:
        """Trigger ``on_startup`` hooks on all middleware instances."""
        _ = self.stack
        for instance in self._instances:
            await instance.on_startup()

    async def on_shutdown(self) -> None:
        """Trigger ``on_shutdown`` hooks on all middleware instances."""
        for instance in self._instances:
            await instance.on_shutdown()

    def add_exception_handler(self, key: int | type[Exception], handler: ExceptionHandler) -> None:
        """Adds a new handler for an exception type or a HTTP status code.

        :param key: Exception type or HTTP status code.
        :param handler: Exception handler.
        """
        self._exception_handlers[key] = handler
        del self.stack

    def add_middleware(self, middleware: Middleware) -> None:
        """Adds a new middleware to the stack.

        :param middleware: Middleware.
        """
        self.middleware.append(middleware)
        del self.stack

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await concurrency.run(self.stack, scope, receive, send)
