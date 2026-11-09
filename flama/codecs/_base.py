import abc
import typing as t

from flama.codecs.types import Decoded, Encoded, NegotiatedCodec

if t.TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Codec", "Negotiator"]


class Codec(t.Generic[Encoded, Decoded], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def decode(self, item: Encoded, **options) -> Decoded: ...


class Negotiator(t.Generic[NegotiatedCodec]):
    def __init__(self, codecs: "Sequence[NegotiatedCodec] | None" = None):
        self.codecs = codecs or []

    @abc.abstractmethod
    def negotiate(self, value: str | None = None, /) -> NegotiatedCodec: ...
