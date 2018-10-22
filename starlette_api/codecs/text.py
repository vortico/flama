from starlette_api import http
from starlette_api.codecs.base import BaseCodec


class TextCodec(BaseCodec):
    media_type = "text/*"
    format = "text"

    async def decode(self, request: http.Request, **options):
        return (await request.body()).decode("utf-8")
