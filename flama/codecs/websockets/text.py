import typing as t

from flama import exceptions
from flama.codecs.base import WebsocketsCodec

if t.TYPE_CHECKING:
    from flama import types

__all__ = ["TextCodec"]


class TextCodec(WebsocketsCodec):
    encoding = "text"

    async def decode(self, item: "types.Message", **options):
        if "text" not in item:
            raise exceptions.DecodeError("Expected text websocket messages")

        return item["text"]
