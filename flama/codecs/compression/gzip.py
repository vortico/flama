from flama._core.compression import Compressor
from flama.codecs.compression.codec import CompressionCodec

__all__ = ["GzipCodec"]


class GzipCodec(CompressionCodec):
    """Gzip compression backend.

    :param level: Compression level (1-9).
    """

    encoding = "gzip"

    def __init__(self, level: int = 9) -> None:
        self._level = level
        self._compressor: Compressor | None = None

    def spawn(self) -> "GzipCodec":
        return GzipCodec(level=self._level)

    async def decode(self, item: tuple[bytes, bool], **options) -> bytes:
        body, finish = item

        if self._compressor is None:
            self._compressor = Compressor("gzip", level=self._level)

        return self._compressor.compress(body, finish)
