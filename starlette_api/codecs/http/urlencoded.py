from starlette_api import http
from starlette_api.codecs.base import HTTPCodec

__all__ = ["URLEncodedCodec"]


class URLEncodedCodec(HTTPCodec):
    media_type = "application/x-www-form-urlencoded"

    async def decode(self, request: http.Request, **options):
        return await request.form() or None
