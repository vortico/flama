import json

from flama import exceptions, types
from flama.codecs.websockets.codec import WebsocketsCodec

__all__ = ["JSONCodec"]


class JSONCodec(WebsocketsCodec):
    encoding = "json"

    async def decode(self, item: types.Message, **options) -> types.JSONSchema:
        if item.get("text") is not None:
            text = item["text"]
        else:
            text = item["bytes"].decode("utf-8")

        try:
            return json.loads(text)
        except json.decoder.JSONDecodeError:
            raise exceptions.DecodeError("Malformed JSON data received")
