from flama._core.compression import Compressor
from flama.codecs.compression.codec import CompressionCodec

__all__ = ["BrotliCodec"]


class BrotliCodec(CompressionCodec):
    """Brotli compression backend.

    :param quality: Compression quality (0--11).
    :param lgwin: Base-2 log of the sliding window size (10--24).
    """

    encoding = "br"

    def __init__(self, quality: int = 4, lgwin: int = 22) -> None:
        self._quality = quality
        self._lgwin = lgwin
        self._compressor: Compressor | None = None

    def spawn(self) -> "BrotliCodec":
        return BrotliCodec(quality=self._quality, lgwin=self._lgwin)

    async def decode(self, item: tuple[bytes, bool], **options) -> bytes:
        body, finish = item

        if self._compressor is None:
            self._compressor = Compressor("brotli", quality=self._quality, lgwin=self._lgwin)

        return self._compressor.compress(body, finish)
