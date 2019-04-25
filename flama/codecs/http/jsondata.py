from flama import exceptions, http
from flama.codecs.base import HTTPCodec

__all__ = ["JSONDataCodec"]


class JSONDataCodec(HTTPCodec):
    media_type = "application/json"
    format = "json"

    async def decode(self, request: http.Request, **options):
        try:
            if await request.body() == b"":
                return None

            return await request.json()
        except ValueError as exc:
            raise exceptions.DecodeError(f"Malformed JSON. {exc}") from None
