import typing as t

__all__ = ["SerializationModelKind", "SerializationCompression", "ProtocolVersion"]


SerializationModelKind = t.Literal["binary", "bundle"]
SerializationCompression = t.Literal["bz2", "lzma", "zlib", "zstd"]
ProtocolVersion = t.Literal[1, 2]
