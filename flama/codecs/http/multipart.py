from flama import http
from flama.codecs.base import HTTPCodec

__all__ = ["MultiPartCodec"]


class MultiPartCodec(HTTPCodec):
    media_type = "multipart/form-data"

    async def decode(self, item: http.Request, **options):
        return await item.form()
