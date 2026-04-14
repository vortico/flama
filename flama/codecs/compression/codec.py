from flama.codecs.base import Codec

__all__ = ["CompressionCodec"]


class CompressionCodec(Codec[tuple[bytes, bool], bytes]):
    encoding: str
