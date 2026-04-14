from flama import exceptions
from flama.codecs.base import Negotiator
from flama.codecs.websockets.codec import WebsocketsCodec

__all__ = ["WebSocketEncodingNegotiator"]


class WebSocketEncodingNegotiator(Negotiator[WebsocketsCodec]):
    def negotiate(self, value: str | None = None, /) -> WebsocketsCodec:
        """
        Given a websocket encoding, return the appropriate codec for decoding the request content.
        """
        if value is None:
            return self.codecs[0]

        for codec in self.codecs:
            if codec.encoding == value:
                return codec

        raise exceptions.NoCodecAvailable(f"Unsupported websocket encoding '{value}'")
