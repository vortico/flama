import json
import typing as t

import starlette.schemas

from flama.http.response import Response
from flama.types.asgi import Receive, Scope, Send

__all__ = ["OpenAPIResponse"]


class OpenAPIResponse(starlette.schemas.OpenAPIResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)

    def render(self, content: t.Any) -> bytes:
        if not isinstance(content, dict):
            raise ValueError("The schema must be a dictionary")

        return json.dumps(content).encode("utf-8")
