import typing

from starlette.middleware.errors import ServerErrorMiddleware as BaseServerErrorMiddleware

from flama.asgi import App
from flama.http import PlainTextResponse, Request, Response


class ServerErrorMiddleware(BaseServerErrorMiddleware):
    def __init__(self, app: App, handler: typing.Optional[typing.Callable] = None, debug: bool = False) -> None:
        self.app = app
        self.handler = handler
        self.debug = debug

    def debug_response(self, request: Request, exc: Exception) -> Response:
        accept = request.headers.get("accept", "")

        if "text/html" in accept:
            ...  # TODO: return HTML error template

        return PlainTextResponse("Internal Server Error", status_code=500)

    def error_response(self, request: Request, exc: Exception) -> Response:
        return PlainTextResponse("Internal Server Error", status_code=500)
