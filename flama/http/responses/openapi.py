import typing as t

from flama._core.json_encoder import encode_json
from flama.http.responses.response import Response

__all__ = ["OpenAPIResponse"]


class OpenAPIResponse(Response):
    media_type = "application/vnd.oai.openapi+json"

    def render(self, content: t.Any) -> bytes:
        if not isinstance(content, dict):
            raise ValueError("The schema must be a dictionary")

        return encode_json(content, compact=True)
