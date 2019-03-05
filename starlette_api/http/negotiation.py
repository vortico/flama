import typing

from starlette_api import exceptions
from starlette_api.http.codecs.base import Codec

__all__ = ["ContentTypeNegotiator"]


class ContentTypeNegotiator:
    def __init__(self, codecs: typing.Optional[typing.List[Codec]] = None):
        self.codecs = codecs or []

    def negotiate(self, content_type: str = None) -> Codec:
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
