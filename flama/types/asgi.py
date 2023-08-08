import sys
import typing as t

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import Concatenate, ParamSpec

    t.Concatenate = Concatenate  # type: ignore
    t.ParamSpec = ParamSpec  # type: ignore

if t.TYPE_CHECKING:
    from flama import endpoints  # noqa

__all__ = [
    "Scope",
    "Message",
    "Receive",
    "Send",
    "AppClass",
    "AppAsyncClass",
    "AppFunction",
    "AppAsyncFunction",
    "App",
    "MiddlewareClass",
    "MiddlewareAsyncClass",
    "MiddlewareFunction",
    "MiddlewareAsyncFunction",
    "Middleware",
    "HTTPHandler",
    "WebSocketHandler",
]

P = t.ParamSpec("P")  # type: ignore # PORT: Remove this comment when stop supporting 3.9
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
class AppClass(t.Protocol[P, R]):
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        ...


class AppAsyncClass(t.Protocol[P, R]):
    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        ...


AppFunction = t.Callable[P, R]
AppAsyncFunction = t.Callable[P, t.Awaitable[R]]
App = t.Union[AppClass, AppAsyncClass, AppFunction, AppAsyncFunction]


# Middleware
class MiddlewareClass(AppClass, t.Protocol[P, R]):
    def __init__(self, app: App, *args: P.args, **kwargs: P.kwargs):
        ...


class MiddlewareAsyncClass(AppAsyncClass, t.Protocol[P, R]):
    def __init__(self, app: App, *args: P.args, **kwargs: P.kwargs):
        ...


MiddlewareFunction = t.Callable[
    t.Concatenate[App, P], App  # type: ignore # PORT: Remove this comment when stop supporting 3.9
]
MiddlewareAsyncFunction = t.Callable[
    t.Concatenate[App, P], t.Awaitable[App]  # type: ignore # PORT: Remove this comment when stop supporting 3.9
]
Middleware = t.Union[t.Type[MiddlewareClass], t.Type[MiddlewareAsyncClass], MiddlewareFunction, MiddlewareAsyncFunction]

HTTPHandler = t.Union[AppFunction, t.Type["endpoints.HTTPEndpoint"]]
WebSocketHandler = t.Union[AppFunction, t.Type["endpoints.WebSocketEndpoint"]]
