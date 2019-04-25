from flama import exceptions, websockets
from flama.codecs.base import WebsocketsCodec

__all__ = ["TextCodec"]


class TextCodec(WebsocketsCodec):
    encoding = "text"

    async def decode(self, message: websockets.Message, **options):
        if "text" not in message:
            raise exceptions.DecodeError("Expected text websocket messages")

        return message["text"]
