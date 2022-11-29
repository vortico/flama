import sys
import typing as t

if sys.version_info >= (3, 8):  # PORT: Remove when stop supporting 3.8 # pragma: no cover
    from typing import Protocol
else:  # pragma: no cover
    from typing_extensions import Protocol

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.10 # pragma: no cover
    from typing import Concatenate, ParamSpec
else:  # pragma: no cover
    from typing_extensions import Concatenate, ParamSpec

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

P = ParamSpec("P")
R = t.TypeVar("R", covariant=True)

Scope = t.NewType("Scope", t.MutableMapping[str, t.Any])
Message = t.NewType("Message", t.MutableMapping[str, t.Any])


class Receive(Protocol):
    async def __call__(self) -> Message:
        ...


class Send(Protocol):
    async def __call__(self, message: Message) -> None:
        ...


# Applications
class AppClass(Protocol[P, R]):
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        ...


class AppAsyncClass(Protocol[P, R]):
    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        ...


AppFunction = t.Callable[..., R]
AppAsyncFunction = t.Callable[..., t.Awaitable[R]]
App = t.Union[AppClass, AppAsyncClass, AppFunction, AppAsyncFunction]


# Middleware
class MiddlewareClass(AppClass):
    def __init__(self, app: App, *args: P.args, **kwargs: P.kwargs):
        ...


class MiddlewareAsyncClass(AppAsyncClass):
    def __init__(self, app: App, *args: P.args, **kwargs: P.kwargs):
        ...


MiddlewareFunction = t.Callable[Concatenate[App, P], App]  # type: ignore[misc]
MiddlewareAsyncFunction = t.Callable[Concatenate[App, P], t.Awaitable[App]]  # type: ignore[misc]
Middleware = t.Union[MiddlewareClass, MiddlewareAsyncClass, MiddlewareFunction, MiddlewareAsyncFunction]

HTTPHandler = t.Union[AppFunction, t.Type["endpoints.HTTPEndpoint"]]
WebSocketHandler = t.Union[AppFunction, t.Type["endpoints.WebSocketEndpoint"]]
