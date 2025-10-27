import typing as t

__all__ = ["Compression", "MLLib", "ProtocolVersion"]


Compression = t.Literal["bz2", "lzma", "zlib", "zstd"]
MLLib = t.Literal["sklearn", "tensorflow", "torch", "keras"]
ProtocolVersion = t.Literal[1]
