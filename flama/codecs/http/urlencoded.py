from flama.codecs.base import HTTPCodec
from flama.types import http

__all__ = ["URLEncodedCodec"]


class URLEncodedCodec(HTTPCodec):
    media_type = "application/x-www-form-urlencoded"

    async def decode(self, request: http.Request, **options):
        return await request.form() or None
