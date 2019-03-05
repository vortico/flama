from starlette_api import exceptions
from starlette_api.websockets.codecs.base import Codec
from starlette_api.websockets.types import Message

__all__ = ["TextCodec"]


class TextCodec(Codec):
    encoding = "text"

    async def decode(self, message: Message, **options):
        if "text" not in message:
            raise exceptions.DecodeError("Expected text websocket messages")

        return message["text"]
