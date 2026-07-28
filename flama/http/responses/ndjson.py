import typing as t

from flama import types
from flama._core.json_encoder import encode_json
from flama.http.responses.response import Payload, StreamingResponse

__all__ = ["NDJSONResponse"]


class NDJSONResponse(StreamingResponse[types.JSONSchema, Payload], t.Generic[Payload]):
    """Streaming JSON-lines response (``application/x-ndjson``).

    Subscript with the schema of a single line, as in ``NDJSONResponse[Item]``, to document the shape
    of the stream. Doing so has no runtime effect.

    Each item produced by the wrapped async iterator is encoded as a single compact JSON object terminated by a
    newline. The response is fully iterator-driven: no length is precomputed, no buffering happens beyond the per-chunk
    encode.
    """

    media_type = "application/x-ndjson"

    def encode(self, chunk: types.JSONSchema) -> bytes:
        return encode_json(chunk, compact=True) + b"\n"
