import typing as t

__all__ = ["SerializationCompression", "Lib", "MLLib", "LLMLib", "ProtocolVersion"]


SerializationCompression = t.Literal["bz2", "lzma", "zlib", "zstd"]
MLLib = t.Literal["sklearn", "tensorflow", "torch", "keras", "transformers"]
LLMLib = t.Literal["vllm"]
Lib = MLLib | LLMLib
ProtocolVersion = t.Literal[1]
