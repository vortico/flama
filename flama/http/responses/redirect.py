import typing as t
from urllib.parse import quote

from flama.http.responses.response import Response

if t.TYPE_CHECKING:
    from collections.abc import Mapping

    from flama.background import BackgroundTask

__all__ = ["RedirectResponse"]


class RedirectResponse(Response):
    def __init__(
        self,
        url: str,
        status_code: int = 307,
        headers: "Mapping[str, str] | None" = None,
        background: "BackgroundTask | None" = None,
    ) -> None:
        super().__init__(content=b"", status_code=status_code, headers=headers, background=background)
        self.headers["location"] = quote(str(url), safe=":/%#?=@[]!$&'()*+,;")
