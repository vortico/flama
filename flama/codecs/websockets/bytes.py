from flama import exceptions, websockets
from flama.codecs.base import WebsocketsCodec

__all__ = ["BytesCodec"]


class BytesCodec(WebsocketsCodec):
    encoding = "bytes"

    async def decode(self, item: websockets.Message, **options):
        if "bytes" not in item:
            raise exceptions.DecodeError("Expected bytes websocket messages")

        return item["bytes"]
