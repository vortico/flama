from flama._core.compression import BrotliCompressor
from flama.codecs.compression.codec import CompressionCodec

__all__ = ["BrotliCodec"]


class BrotliCodec(CompressionCodec):
    """Brotli compression backend.

    :param quality: Compression quality (0--11).
    :param lgwin: Base-2 log of the sliding window size (10--24).
    """

    encoding = "br"

    def __init__(self, quality: int = 4, lgwin: int = 22) -> None:
        self.compressor = BrotliCompressor(quality, lgwin)

    async def decode(self, item: tuple[bytes, bool], **options) -> bytes:
        body, finish = item

        return self.compressor.compress(body, finish)
