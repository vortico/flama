import json

from flama import exceptions, websockets
from flama.codecs.base import WebsocketsCodec

__all__ = ["JSONCodec"]


class JSONCodec(WebsocketsCodec):
    encoding = "json"

    async def decode(self, message: websockets.Message, **options):
        if message.get("text") is not None:
            text = message["text"]
        else:
            text = message["bytes"].decode("utf-8")

        try:
            return json.loads(text)
        except json.decoder.JSONDecodeError:
            raise exceptions.DecodeError("Malformed JSON data received")
