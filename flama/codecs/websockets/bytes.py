from flama import exceptions, types
from flama.codecs.websockets.codec import WebsocketsCodec

__all__ = ["BytesCodec"]


class BytesCodec(WebsocketsCodec):
    encoding = "bytes"

    async def decode(self, item: types.Message, **options) -> bytes:
        if "bytes" not in item:
            raise exceptions.DecodeError("Expected bytes websocket messages")

        return item["bytes"]
