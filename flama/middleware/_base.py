import typing as t

from flama import _concurrency, types

if t.TYPE_CHECKING:
    from flama.errors.types import ExceptionHandlerFunction

__all__ = ["Middleware", "MiddlewareStack", "RootMiddlewareStack"]


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
        await _concurrency.run(self.app, scope, receive, send)


class MiddlewareStack:
    """Ordered middleware chain with lifecycle management, for a mounted application.

    Builds an ASGI pipeline by wrapping the application router with each middleware in order, inside an
    :class:`ExceptionMiddleware` that handles only the exceptions handlers are registered for, so whatever the
    application leaves unhandled reaches its parents.

    :param app: The Flama application.
    :param middleware: Sequence of :class:`Middleware` instances.
    :param debug: Whether to enable debug mode on error middleware.
    """

    def __init__(self, app: "types.App", middleware: t.Sequence[Middleware], debug: bool) -> None:
        self.app = app
        self.middleware = list(reversed(middleware))
        self.debug = debug
        self._exception_handlers: dict[int | type[Exception], ExceptionHandlerFunction] = {}
        self._pipeline: types.ASGIApp | None = None
        self._instances: list[t.Any] = []

    @classmethod
    def from_stack(cls, stack: "MiddlewareStack", /) -> t.Self:
        """Build a stack of this kind with the middleware and exception handlers of another.

        :param stack: Stack to take them from.
        :return: The new stack.
        """
        result = cls(stack.app, list(reversed(stack.middleware)), stack.debug)
        result._exception_handlers = dict(stack._exception_handlers)
        return result

    @property
    def stack(self) -> "types.ASGIApp":
        if self._pipeline is None:
            self._instances.clear()
            app: types.ASGIApp = self.app.router
            for m in self._stack():
                m._build(app)
                self._instances.append(m)
                app = t.cast(types.ASGIApp, m)

            self._pipeline = app

        return self._pipeline

    @stack.deleter
    def stack(self):
        self._pipeline = None
        self._instances.clear()

    def _stack(self) -> list[_BaseMiddleware]:
        """The middleware wrapping the router, innermost first.

        :return: Middleware list.
        """
        from flama.errors.middleware import ExceptionMiddleware

        return [ExceptionMiddleware(handlers=self._exception_handlers, debug=self.debug), *self.middleware]

    async def on_startup(self) -> None:
        """Trigger ``on_startup`` hooks on all middleware instances."""
        _ = self.stack
        for instance in self._instances:
            await instance.on_startup()

    async def on_shutdown(self) -> None:
        """Trigger ``on_shutdown`` hooks on all middleware instances."""
        for instance in self._instances:
            await instance.on_shutdown()

    def add_exception_handler(self, key: int | type[Exception], handler: "ExceptionHandlerFunction") -> None:
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
        await _concurrency.run(self.stack, scope, receive, send)


class RootMiddlewareStack(MiddlewareStack):
    """Middleware chain of the root application, which also answers what nothing else handled.

    Flama's exceptions and repository errors get their default answers unless a handler is registered for their
    class, and a :class:`ServerErrorMiddleware` outside the declared middleware answers anything left.
    """

    def _stack(self) -> list[_BaseMiddleware]:
        from flama.ddd.exception_handlers import RepositoryExceptionHandler
        from flama.errors.exception_handlers import (
            HTTPExceptionHandler,
            JSONRPCExceptionHandler,
            RoutingExceptionHandler,
            WebSocketExceptionHandler,
        )
        from flama.errors.middleware import ExceptionMiddleware, ServerErrorMiddleware

        defaults: dict[int | type[Exception], ExceptionHandlerFunction] = {
            handler.exc_class: handler
            for handler in (
                HTTPExceptionHandler(debug=self.debug),
                JSONRPCExceptionHandler(),
                WebSocketExceptionHandler(),
                RoutingExceptionHandler(debug=self.debug),
                RepositoryExceptionHandler(),
            )
        }

        return [
            ExceptionMiddleware(handlers={**defaults, **self._exception_handlers}, debug=self.debug),
            *self.middleware,
            ServerErrorMiddleware(debug=self.debug),
        ]
