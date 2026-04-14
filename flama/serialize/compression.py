import enum
from collections.abc import Callable

from flama import types
from flama._core.compression import (
    compress_bz2,
    compress_lzma,
    compress_zlib,
    compress_zstd,
    decompress_bz2,
    decompress_lzma,
    decompress_zlib,
    decompress_zstd,
)

__all__ = ["CompressionFormat", "Compression"]


class CompressionFormat(enum.IntEnum):
    """Supported compression formats for ML model serialization.

    Integer values are stable and used in the binary serialization header.
    """

    bz2 = 1
    lzma = 2
    zlib = 3
    zstd = 4


_COMPRESSORS: dict[CompressionFormat, tuple[Callable[[bytes], bytes], Callable[[bytes], bytes]]] = {
    CompressionFormat.bz2: (compress_bz2, decompress_bz2),
    CompressionFormat.lzma: (compress_lzma, decompress_lzma),
    CompressionFormat.zlib: (compress_zlib, decompress_zlib),
    CompressionFormat.zstd: (compress_zstd, decompress_zstd),
}


class Compression:
    """A utility class to handle bytes compression and decompression using various supported formats.

    All compression is backed by the Rust ``_core.compression`` module.
    """

    format: CompressionFormat

    def __init__(self, format: int | types.SerializationCompression) -> None:
        """Initializes the Compression utility with a specific compression format.

        Accepts either the integer id stored in the binary protocol header or a string name
        matching :data:`~flama.types.SerializationCompression`.

        :param format: The desired compression format.
        :raises ValueError: If the provided format is not supported.
        """
        try:
            self.format = CompressionFormat(format) if isinstance(format, int) else CompressionFormat[format]
            self._compress, self._decompress = _COMPRESSORS[self.format]
        except (KeyError, ValueError):
            raise ValueError(f"Wrong format '{format}'")

    def compress(self, b: bytes, /) -> bytes:
        """Compress a bytes string.

        :param b: Raw bytes string.
        :return: Compressed bytes string.
        """
        return self._compress(b)

    def decompress(self, b: bytes, /) -> bytes:
        """Decompress a bytes string.

        :param b: Compressed bytes string.
        :return: Raw bytes string.
        """
        return self._decompress(b)
