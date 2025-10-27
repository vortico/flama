import typing as t

from flama import types

if t.TYPE_CHECKING:
    from flama import http

HandlerException = t.TypeVar("HandlerException", bound=Exception)
Handler = t.Callable[
    [types.Scope, types.Receive, types.Send, HandlerException],
    "http.Response | None" | t.Awaitable["http.Response | None"],
]
