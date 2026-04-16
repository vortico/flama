import http
import typing as t
from urllib.parse import quote

from flama import types
from flama.http.responses.response import Response

if t.TYPE_CHECKING:
    from collections.abc import Mapping

    from flama.background import BackgroundTask

__all__ = ["RedirectResponse"]


class RedirectResponse(Response):
    def __init__(
        self,
        url: str,
        status_code: int = http.HTTPStatus.TEMPORARY_REDIRECT,
        headers: "Mapping[str, str] | None" = None,
        background: "BackgroundTask | None" = None,
    ) -> None:
        self.url = url
        super().__init__(
            status_code=status_code,
            headers={**(headers or {}), "location": quote(str(self.url), safe=":/%#?=@[]!$&'()*+,;")},
            background=background,
        )

    async def _send_response(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await send(
            types.Message({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
        )
        await send(types.Message({"type": "http.response.body", "body": b""}))
