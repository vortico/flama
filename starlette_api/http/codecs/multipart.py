from starlette_api import http
from starlette_api.http.codecs.base import Codec

__all__ = ["MultiPartCodec"]


class MultiPartCodec(Codec):
    media_type = "multipart/form-data"

    async def decode(self, request: http.Request, **options):
        return await request.form()
