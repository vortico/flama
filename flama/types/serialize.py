import typing as t

__all__ = ["SerializationCompression", "MLLib", "ProtocolVersion"]


SerializationCompression = t.Literal["bz2", "lzma", "zlib", "zstd"]
MLLib = t.Literal["sklearn", "tensorflow", "torch", "keras", "transformers"]
ProtocolVersion = t.Literal[1]
