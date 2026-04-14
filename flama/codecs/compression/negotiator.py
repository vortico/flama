from flama import exceptions
from flama.codecs.base import Negotiator
from flama.codecs.compression.codec import CompressionCodec

__all__ = ["CompressionNegotiator"]


class CompressionNegotiator(Negotiator[CompressionCodec]):
    def negotiate(self, value: str | None = None, /) -> CompressionCodec:
        """Select the best compression backend for the given header value.

        Walks the configured backends in priority order and returns the first whose encoding token appears in the
        ``Accept-Encoding`` set.

        :param accept_encoding: Raw ``Accept-Encoding`` header value.
        :return: Matching backend or ``None``.
        """
        accepted = {encoding.strip().split(";")[0].strip().lower() for encoding in (value or "").split(",")}
        for backend in self.codecs:
            if backend.encoding in accepted:
                return backend

        raise exceptions.NoCodecAvailable(f"Unsupported encoding in Accept-Encoding header '{value}'")
