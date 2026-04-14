import typing as t

from flama.codecs.http.codec import HTTPCodec

if t.TYPE_CHECKING:
    from flama.http import Request

__all__ = ["URLEncodedCodec"]


class URLEncodedCodec(HTTPCodec):
    media_type = "application/x-www-form-urlencoded"

    async def decode(self, item: "Request", **options) -> dict[str, t.Any] | None:
        if form := await item.form():
            return dict(form)

        return None
