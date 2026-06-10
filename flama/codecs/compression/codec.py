import abc

from flama.codecs._base import Codec

__all__ = ["CompressionCodec"]


class CompressionCodec(Codec[tuple[bytes, bool], bytes]):
    encoding: str

    @abc.abstractmethod
    def spawn(self) -> "CompressionCodec":
        """Return a fresh, unused codec for a single response.

        The underlying compressor is single-use (finishing it once exhausts it) and stateful across the chunks of one
        response, so a codec instance cannot be shared between requests: doing so fails on reuse and corrupts
        concurrent streams. The negotiator calls this per request to hand out isolated state.
        """
        ...
