import typing as t

import starlette.responses

from flama._core.json_encoder import encode_json
from flama.types.asgi import Receive, Scope, Send

__all__ = [
    "Response",
    "HTMLResponse",
    "PlainTextResponse",
    "JSONResponse",
    "RedirectResponse",
    "StreamingResponse",
    "FileResponse",
]


class Response(starlette.responses.Response):
    async def __call__(  # ty: ignore[invalid-method-override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        await super().__call__(scope, receive, send)  # ty: ignore[invalid-argument-type]

    def __hash__(self) -> int:
        return hash(
            (
                self.status_code,
                getattr(self, "media_type"),
                self.background,
                self.body,
                self.headers,
            )
        )

    def __eq__(self, value: object, /) -> bool:
        return (
            isinstance(value, Response)
            and self.status_code == value.status_code
            and getattr(self, "media_type") == getattr(value, "media_type")
            and self.background == value.background
            and self.body == value.body
            and self.headers == value.headers
        )


class HTMLResponse(starlette.responses.HTMLResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)


class PlainTextResponse(starlette.responses.PlainTextResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)


class JSONResponse(starlette.responses.JSONResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)

    def render(self, content: t.Any) -> bytes:
        return encode_json(content, compact=True)


class RedirectResponse(starlette.responses.RedirectResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)


class StreamingResponse(starlette.responses.StreamingResponse, Response):
    async def __call__(  # ty: ignore[invalid-method-override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        await super().__call__(scope, receive, send)  # ty: ignore[invalid-argument-type]


class FileResponse(starlette.responses.FileResponse, Response):
    async def __call__(  # ty: ignore[invalid-method-override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        await super().__call__(scope, receive, send)  # ty: ignore[invalid-argument-type]
