import json
import typing as t

from flama import exceptions
from flama.codecs.base import WebsocketsCodec

if t.TYPE_CHECKING:
    from flama import types

__all__ = ["JSONCodec"]


class JSONCodec(WebsocketsCodec):
    encoding = "json"

    async def decode(self, item: "types.Message", **options):
        if item.get("text") is not None:
            text = item["text"]
        else:
            text = item["bytes"].decode("utf-8")

        try:
            return json.loads(text)
        except json.decoder.JSONDecodeError:
            raise exceptions.DecodeError("Malformed JSON data received")
