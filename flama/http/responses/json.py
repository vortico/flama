import typing as t

from flama._core.json_encoder import encode_json
from flama.http.responses.response import Response

__all__ = ["JSONResponse"]


class JSONResponse(Response):
    media_type = "application/json"

    def render(self, content: t.Any) -> bytes:
        return encode_json(content, compact=True)
