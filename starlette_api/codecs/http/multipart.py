from starlette_api import http
from starlette_api.codecs.base import HTTPCodec

__all__ = ["MultiPartCodec"]


class MultiPartCodec(HTTPCodec):
    media_type = "multipart/form-data"

    async def decode(self, request: http.Request, **options):
        return await request.form()
