import typing as t

from flama.codecs.base import HTTPCodec

if t.TYPE_CHECKING:
    from flama import http

__all__ = ["URLEncodedCodec"]


class URLEncodedCodec(HTTPCodec):
    media_type = "application/x-www-form-urlencoded"

    async def decode(self, item: "http.Request", **options):
        return await item.form() or None
