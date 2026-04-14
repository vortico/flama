from flama._core.compression import GzipCompressor
from flama.codecs.compression.codec import CompressionCodec

__all__ = ["GzipCodec"]


class GzipCodec(CompressionCodec):
    """Gzip compression backend.

    :param level: Compression level (1-9).
    """

    encoding = "gzip"

    def __init__(self, level: int = 9) -> None:
        self.compressor = GzipCompressor(level)

    async def decode(self, item: tuple[bytes, bool], **options) -> bytes:
        body, finish = item

        return self.compressor.compress(body, finish)
