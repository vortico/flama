from pathlib import Path

from flama.asgi import App, Message, Receive, Scope, Send
from flama.http import PlainTextResponse, Request, Response
from flama.responses import HTMLTemplateResponse

TEMPLATES_PATH = Path(__file__).parents[1].resolve() / "templates" / "debug"


class ServerErrorMiddleware:
    def __init__(self, app: App, debug: bool = False) -> None:
        self.app = app
        self.debug = debug

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def _send(message: Message) -> None:
            nonlocal response_started, send

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as exc:
            request = Request(scope)
            response = self.debug_response(request, exc) if self.debug else self.error_response(request, exc)

            if not response_started:
                await response(scope, receive, send)

            # We always continue to raise the exception.
            # This allows servers to log the error, or test clients to optionally raise the error within the test case.
            raise exc

    def debug_response(self, request: Request, exc: Exception) -> Response:
        accept = request.headers.get("accept", "")

        if "text/html" in accept:
            return HTMLTemplateResponse("debug/error_500.html")
        return PlainTextResponse("Internal Server Error", status_code=500)

    def error_response(self, request: Request, exc: Exception) -> Response:
        return PlainTextResponse("Internal Server Error", status_code=500)
