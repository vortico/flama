from starlette_api import exceptions, websockets
from starlette_api.codecs.base import WebsocketsCodec

__all__ = ["BytesCodec"]


class BytesCodec(WebsocketsCodec):
    encoding = "bytes"

    async def decode(self, message: websockets.Message, **options):
        if "bytes" not in message:
            raise exceptions.DecodeError("Expected bytes websocket messages")

        return message["bytes"]
