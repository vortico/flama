import typing as t

from flama import exceptions
from flama.codecs.base import HTTPCodec

if t.TYPE_CHECKING:
    from flama import http

__all__ = ["JSONDataCodec"]


class JSONDataCodec(HTTPCodec):
    media_type = "application/json"
    format = "json"

    async def decode(self, item: "http.Request", **options):
        try:
            if await item.body() == b"":
                return None

            return await item.json()
        except ValueError as exc:
            raise exceptions.DecodeError(f"Malformed JSON. {exc}") from None
