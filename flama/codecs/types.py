import typing as t

if t.TYPE_CHECKING:
    from flama.codecs._base import Codec

__all__ = ["Decoded", "Encoded", "NegotiatedCodec"]

Encoded = t.TypeVar("Encoded")
Decoded = t.TypeVar("Decoded")
NegotiatedCodec = t.TypeVar("NegotiatedCodec", bound="Codec")
