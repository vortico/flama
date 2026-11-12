import typing as t

from flama import types

if t.TYPE_CHECKING:
    from flama.http import Response

__all__ = ["ExceptionHandlerFunction"]

E = t.TypeVar("E", bound=Exception)
ExceptionHandlerFunction = t.Callable[
    [types.Scope, types.Receive, types.Send, E], "Response | None | t.Awaitable[Response | None]"
]
