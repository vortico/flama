from flama import types
from flama.http.requests.http import Request
from flama.http.requests.websocket import WebSocket
from flama.http.responses.response import Response
from flama.injection import context

__all__ = ["Context"]


class Context(context.Context):
    scope = context.Field(types.Scope)
    receive = context.Field(types.Receive)
    send = context.Field(types.Send)
    exc = context.Field(Exception, required=False)
    app = context.Field(types.App)
    route = context.Field(types.BaseRoute)
    request = context.Field(Request, hashable=False)
    response = context.Field(Response, required=False)
    websocket = context.Field(WebSocket, hashable=False)
    websocket_message = context.Field(types.Message, required=False)
    websocket_encoding = context.Field(types.Encoding, required=False)
    websocket_code = context.Field(types.Code, required=False)
