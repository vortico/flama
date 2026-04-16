from flama import types
from flama._core.json_encoder import encode_json
from flama.http.responses.response import BufferedResponse

__all__ = ["JSONResponse"]


class JSONResponse(BufferedResponse[types.JSONSchema]):
    media_type = "application/json"

    def render(self, content: types.JSONSchema) -> bytes:
        return encode_json(content, compact=True)
