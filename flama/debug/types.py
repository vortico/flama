import typing as t

from flama import types

if t.TYPE_CHECKING:
    from flama import http

HandlerException = t.TypeVar("HandlerException", bound=Exception)
Handler = t.Callable[
    [types.Scope, types.Receive, types.Send, HandlerException],
    t.Union[t.Optional["http.Response"], t.Awaitable[None], t.Awaitable[t.Optional["http.Response"]]],
]
