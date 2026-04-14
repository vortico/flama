import typing as t

from flama.codecs.http.codec import HTTPCodec

if t.TYPE_CHECKING:
    from flama.http import Request

__all__ = ["MultiPartCodec"]


class MultiPartCodec(HTTPCodec):
    media_type = "multipart/form-data"

    async def decode(self, item: "Request", **options) -> dict[str, t.Any] | None:
        if form := await item.form():
            return dict(form)

        return None
