from starlette_api import exceptions
from starlette_api.websockets.codecs.base import Codec
from starlette_api.websockets.types import Message

__all__ = ["BytesCodec"]


class BytesCodec(Codec):
    encoding = "bytes"

    async def decode(self, message: Message, **options):
        if "bytes" not in message:
            raise exceptions.DecodeError("Expected bytes websocket messages")

        return message["bytes"]
