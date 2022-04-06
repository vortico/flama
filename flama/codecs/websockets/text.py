from flama import exceptions, websockets
from flama.codecs.base import WebsocketsCodec

__all__ = ["TextCodec"]


class TextCodec(WebsocketsCodec):
    encoding = "text"

    async def decode(self, item: websockets.Message, **options):
        if "text" not in item:
            raise exceptions.DecodeError("Expected text websocket messages")

        return item["text"]
