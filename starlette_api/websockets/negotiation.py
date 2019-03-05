import typing

from starlette_api import exceptions
from starlette_api.websockets.codecs import BytesCodec
from starlette_api.websockets.codecs.base import Codec

__all__ = ["WebSocketEncodingNegotiator"]


class WebSocketEncodingNegotiator:
    def __init__(self, codecs: typing.Optional[typing.List[Codec]] = None):
        self.codecs = codecs or [BytesCodec()]

    def negotiate(self, encoding: str = None) -> Codec:
        """
        Given a websocket encoding, return the appropriate codec for decoding the request content.
        """
        if encoding is None:
            return self.codecs[0]

        for codec in self.codecs:
            if codec.encoding == encoding:
                return codec

        raise exceptions.NoCodecAvailable(f"Unsupported websocket encoding '{encoding}'")
