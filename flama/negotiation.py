import typing

from flama import exceptions
from flama.codecs.base import HTTPCodec, WebsocketsCodec
from flama.codecs.websockets import BytesCodec

__all__ = ["ContentTypeNegotiator", "WebSocketEncodingNegotiator"]


class ContentTypeNegotiator:
    def __init__(self, codecs: typing.Optional[typing.List[HTTPCodec]] = None):
        self.codecs = codecs or []

    def negotiate(self, content_type: str = None) -> WebsocketsCodec:
        """
        Given the value of a 'Content-Type' header, return the appropriate codec for decoding the request content.
        """
        if content_type is None:
            return self.codecs[0]

        content_type = content_type.split(";")[0].strip().lower()
        main_type = content_type.split("/")[0] + "/*"
        wildcard_type = "*/*"

        for codec in self.codecs:
            if codec.media_type in (content_type, main_type, wildcard_type):
                return codec

        raise exceptions.NoCodecAvailable(f"Unsupported media in Content-Type header '{content_type}'")


class WebSocketEncodingNegotiator:
    def __init__(self, codecs: typing.Optional[typing.List[WebsocketsCodec]] = None):
        self.codecs = codecs or [BytesCodec()]

    def negotiate(self, encoding: str = None) -> WebsocketsCodec:
        """
        Given a websocket encoding, return the appropriate codec for decoding the request content.
        """
        if encoding is None:
            return self.codecs[0]

        for codec in self.codecs:
            if codec.encoding == encoding:
                return codec

        raise exceptions.NoCodecAvailable(f"Unsupported websocket encoding '{encoding}'")
