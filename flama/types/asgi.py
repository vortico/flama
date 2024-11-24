import typing as t

from flama import compat

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
]

P = compat.ParamSpec("P")  # PORT: Replace compat when stop supporting 3.9
R = t.TypeVar("R", covariant=True)

Scope = t.NewType("Scope", t.MutableMapping[str, t.Any])
Message = t.NewType("Message", t.MutableMapping[str, t.Any])


class Receive(t.Protocol):
    async def __call__(self) -> Message:
        ...


class Send(t.Protocol):
    async def __call__(self, message: Message) -> None:
        ...


# Applications
@t.runtime_checkable
class AppClass(t.Protocol):
    def __call__(self, scope: Scope, receive: Receive, send: Send) -> t.Union[None, t.Awaitable[None]]:
        ...


AppFunction = t.Callable[[Scope, Receive, Send], t.Union[None, t.Awaitable[None]]]
App = t.Union[AppClass, AppFunction]


# Middleware
@t.runtime_checkable
class MiddlewareClass(AppClass, t.Protocol[P, R]):
    def __init__(self, app: App, *args: P.args, **kwargs: P.kwargs):
        ...


MiddlewareFunction = t.Callable[compat.Concatenate[App, P], App]  # PORT: Replace compat when stop supporting 3.9
Middleware = t.Union[type[MiddlewareClass], MiddlewareFunction]

HTTPHandler = t.Union[t.Callable, type["endpoints.HTTPEndpoint"]]
WebSocketHandler = t.Union[t.Callable, type["endpoints.WebSocketEndpoint"]]
