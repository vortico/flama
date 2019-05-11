from flama import exceptions
from flama.codecs.base import WebsocketsCodec
from flama.types import websockets

__all__ = ["TextCodec"]


class TextCodec(WebsocketsCodec):
    encoding = "text"

    async def decode(self, message: websockets.Message, **options):
        if "text" not in message:
            raise exceptions.DecodeError("Expected text websocket messages")

        return message["text"]
