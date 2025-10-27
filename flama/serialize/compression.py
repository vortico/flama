import enum
import typing as t
from types import ModuleType

from flama import compat, types

__all__ = ["CompressionFormat", "Compression"]


class CompressionFormat(enum.Enum):
    """Defines the supported compression formats.

    Each member corresponds to a specific compression algorithm that can be used for serializing ML models.
    """

    bz2 = enum.auto()
    lzma = enum.auto()
    zlib = enum.auto()
    zstd = enum.auto()


class Compression:
    """A utility class to handle bytes compression and decompression using various supported formats.

    This class acts as a wrapper around the standard or compatible Python compression modules (bz2, lzma, zlib, zstd).
    """

    _modules: t.Final[dict[CompressionFormat, ModuleType]] = {
        CompressionFormat.bz2: compat.bz2,  # PORT: Replace compat when stop supporting 3.13
        CompressionFormat.lzma: compat.lzma,  # PORT: Replace compat when stop supporting 3.13
        CompressionFormat.zlib: compat.zlib,  # PORT: Replace compat when stop supporting 3.13
        CompressionFormat.zstd: compat.zstd,  # PORT: Replace compat when stop supporting 3.13
    }

    def __init__(self, format: int | types.Compression) -> None:
        """Initializes the Compression utility with a specific compression format.

        The format can be specified as an integer value corresponding to the :class:`CompressionFormat` enum member or
        as the string name of the format.

        :param format: The desired compression format. Can be an integer value or a string name
        from :class:`CompressionFormat`.
        :raises ValueError: If the provided format is not a valid :class:`CompressionFormat` member.
        """
        try:
            self.format = CompressionFormat(format) if isinstance(format, int) else CompressionFormat[format]
            self._module = self._modules[self.format]
        except KeyError:
            raise ValueError(f"Wrong format '{format}'")

    def compress(self, b: bytes, /) -> bytes:
        """Compress a bytes string.

        :param b: Raw bytes string.
        :return: Compressed bytes string.
        """
        return self._module.compress(b)

    def decompress(self, b: bytes, /) -> bytes:
        """Decompress a bytes string.

        :param b: Compressed bytes string.
        :return: Raw bytes string.
        """
        return self._module.decompress(b)
