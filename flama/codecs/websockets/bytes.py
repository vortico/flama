from flama import exceptions
from flama.codecs.base import WebsocketsCodec
from flama.types import websockets

__all__ = ["BytesCodec"]


class BytesCodec(WebsocketsCodec):
    encoding = "bytes"

    async def decode(self, message: websockets.Message, **options):
        if "bytes" not in message:
            raise exceptions.DecodeError("Expected bytes websocket messages")

        return message["bytes"]
