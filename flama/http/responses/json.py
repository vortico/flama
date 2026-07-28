import typing as t

from flama import types
from flama._core.json_encoder import encode_json
from flama.http.responses.response import BufferedResponse, Payload

__all__ = ["JSONResponse"]


class JSONResponse(BufferedResponse[types.JSONSchema, Payload], t.Generic[Payload]):
    """JSON response (``application/json``).

    Subscript with the schema of the body, as in ``JSONResponse[Item]``, to document its shape. Doing
    so has no runtime effect.
    """

    media_type = "application/json"

    def render(self, content: types.JSONSchema) -> bytes:
        return encode_json(content, compact=True)
