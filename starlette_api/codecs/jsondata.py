from starlette_api import exceptions, http
from starlette_api.codecs.base import BaseCodec


class JSONCodec(BaseCodec):
    media_type = "application/json"
    format = "json"

    async def decode(self, request: http.Request, **options):
        try:
            if await request.body() == b"":
                return None

            return await request.json()
        except ValueError as exc:
            raise exceptions.ParseError("Malformed JSON. %s" % exc) from None
