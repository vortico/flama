from flama import http
from flama.codecs.base import HTTPCodec

__all__ = ["URLEncodedCodec"]


class URLEncodedCodec(HTTPCodec):
    media_type = "application/x-www-form-urlencoded"

    async def decode(self, item: http.Request, **options):
        return await item.form() or None
