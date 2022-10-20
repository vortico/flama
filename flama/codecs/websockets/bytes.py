import typing as t

from flama import exceptions
from flama.codecs.base import WebsocketsCodec

if t.TYPE_CHECKING:
    from flama import types

__all__ = ["BytesCodec"]


class BytesCodec(WebsocketsCodec):
    encoding = "bytes"

    async def decode(self, item: "types.Message", **options):
        if "bytes" not in item:
            raise exceptions.DecodeError("Expected bytes websocket messages")

        return item["bytes"]
