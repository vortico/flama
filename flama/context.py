import dataclasses

from flama import types
from flama.http.requests.http import Request
from flama.http.requests.websocket import WebSocket
from flama.http.responses.response import Response
from flama.injection.context import Context as BaseContext

__all__ = ["Context"]


@dataclasses.dataclass(eq=False)
class Context(BaseContext):
    scope: types.Scope | None = None
    receive: types.Receive | None = None
    send: types.Send | None = None
    exc: Exception | None = None
    app: types.App | None = None
    route: types.BaseRoute | None = None
    request: Request | None = None
    response: Response | None = None
    websocket: WebSocket | None = None
    websocket_message: types.Message | None = None
    websocket_encoding: types.Encoding | None = None
    websocket_code: types.Code | None = None

    __hashable__ = (
        "scope",
        "receive",
        "send",
        "exc",
        "app",
        "route",
        "response",
        "websocket_message",
        "websocket_encoding",
        "websocket_code",
    )
