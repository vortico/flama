from starlette_api import http
from starlette_api.codecs.base import BaseCodec


class URLEncodedCodec(BaseCodec):
    media_type = "application/x-www-form-urlencoded"

    async def decode(self, request: http.Request, **options):
        return await request.form() or None
