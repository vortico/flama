import typing as t

from flama.codecs.base import HTTPCodec

if t.TYPE_CHECKING:
    from flama import http

__all__ = ["MultiPartCodec"]


class MultiPartCodec(HTTPCodec):
    media_type = "multipart/form-data"

    async def decode(self, item: "http.Request", **options) -> t.Any:
        return await item.form()
