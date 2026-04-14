import typing as t

from flama import exceptions
from flama.codecs.base import Negotiator
from flama.codecs.http.codec import HTTPCodec

if t.TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["HTTPContentTypeNegotiator"]


class HTTPContentTypeNegotiator(Negotiator[HTTPCodec]):
    def __init__(self, codecs: "Sequence[HTTPCodec] | None" = None):
        self.codecs = codecs or []

    def negotiate(self, value: str | None = None, /) -> HTTPCodec:
        """
        Given the value of a 'Content-Type' header, return the appropriate codec for decoding the request content.
        """
        if value is None:
            return self.codecs[0]

        value = value.split(";")[0].strip().lower()
        main_type = value.split("/")[0] + "/*"
        wildcard_type = "*/*"

        for codec in self.codecs:
            if codec.media_type in (value, main_type, wildcard_type):
                return codec

        raise exceptions.NoCodecAvailable(f"Unsupported media in Content-Type header '{value}'")
