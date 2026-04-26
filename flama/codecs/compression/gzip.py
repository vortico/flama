from flama.codecs.compression.codec import CompressionCodec
from flama.compression import Compressor

__all__ = ["GzipCodec"]


class GzipCodec(CompressionCodec):
    """Gzip compression backend.

    :param level: Compression level (1-9).
    """

    encoding = "gzip"

    def __init__(self, level: int = 9) -> None:
        self._compressor = Compressor("gzip", level=level)

    async def decode(self, item: tuple[bytes, bool], **options) -> bytes:
        body, finish = item

        return self._compressor.compress(body, finish)
