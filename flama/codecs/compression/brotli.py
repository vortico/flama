from flama.codecs.compression.codec import CompressionCodec
from flama.compression import Compressor

__all__ = ["BrotliCodec"]


class BrotliCodec(CompressionCodec):
    """Brotli compression backend.

    :param quality: Compression quality (0--11).
    :param lgwin: Base-2 log of the sliding window size (10--24).
    """

    encoding = "br"

    def __init__(self, quality: int = 4, lgwin: int = 22) -> None:
        self._compressor = Compressor("brotli", quality=quality, lgwin=lgwin)

    async def decode(self, item: tuple[bytes, bool], **options) -> bytes:
        body, finish = item

        return self._compressor.compress(body, finish)
