import typing as t

if t.TYPE_CHECKING:
    from flama import endpoints

__all__ = [
    "Scope",
    "Message",
    "Receive",
    "Send",
    "AppClass",
    "AppFunction",
    "App",
    "MiddlewareClass",
    "MiddlewareFunction",
    "Middleware",
    "HTTPHandler",
    "WebSocketHandler",
    "Handler",
]

P = t.ParamSpec("P")
R = t.TypeVar("R", covariant=True)


class Scope(dict[str, t.Any]): ...


class Message(dict[str, t.Any]): ...


class Receive(t.Protocol):
    async def __call__(self) -> Message: ...


class Send(t.Protocol):
    async def __call__(self, message: Message) -> None: ...


# Applications
@t.runtime_checkable
class AppClass(t.Protocol):
    def __call__(self, scope: Scope, receive: Receive, send: Send) -> None | t.Awaitable[None]: ...


AppFunction = t.Callable[[Scope, Receive, Send], None | t.Awaitable[None]]
App = AppClass | AppFunction


# Middleware
@t.runtime_checkable
class MiddlewareClass(AppClass, t.Protocol[P, R]):
    def __init__(self, app: App, *args: P.args, **kwargs: P.kwargs): ...


MiddlewareFunction = t.Callable[t.Concatenate[App, P], App]
Middleware = type[MiddlewareClass] | MiddlewareFunction

HTTPHandler = t.Callable | type["endpoints.HTTPEndpoint"]
WebSocketHandler = t.Callable | type["endpoints.WebSocketEndpoint"]
Handler = HTTPHandler | WebSocketHandler
