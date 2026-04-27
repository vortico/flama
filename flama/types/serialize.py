import typing as t

__all__ = ["SerializationCompression", "ProtocolVersion"]


SerializationCompression = t.Literal["bz2", "lzma", "zlib", "zstd"]
ProtocolVersion = t.Literal[1]
