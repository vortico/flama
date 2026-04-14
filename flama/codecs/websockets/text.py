from flama import exceptions, types
from flama.codecs.websockets.codec import WebsocketsCodec

__all__ = ["TextCodec"]


class TextCodec(WebsocketsCodec):
    encoding = "text"

    async def decode(self, item: types.Message, **options) -> str:
        if "text" not in item:
            raise exceptions.DecodeError("Expected text websocket messages")

        return item["text"]
