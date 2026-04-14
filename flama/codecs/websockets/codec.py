from flama import types
from flama.codecs.base import Codec

__all__ = ["WebsocketsCodec"]


class WebsocketsCodec(Codec[types.Message, bytes | str | types.JSONSchema | None]):
    encoding: str | None = None
