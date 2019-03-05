import json

from starlette_api import exceptions
from starlette_api.websockets.codecs.base import Codec
from starlette_api.websockets.types import Message

__all__ = ["JSONCodec"]


class JSONCodec(Codec):
    encoding = "json"

    async def decode(self, message: Message, **options):
        if message.get("text") is not None:
            text = message["text"]
        else:
            text = message["bytes"].decode("utf-8")

        try:
            return json.loads(text)
        except json.decoder.JSONDecodeError:
            raise exceptions.DecodeError("Malformed JSON data received")
