from starlette_api import http
from starlette_api.http.codecs.base import Codec

__all__ = ["URLEncodedCodec"]


class URLEncodedCodec(Codec):
    media_type = "application/x-www-form-urlencoded"

    async def decode(self, request: http.Request, **options):
        return await request.form() or None
