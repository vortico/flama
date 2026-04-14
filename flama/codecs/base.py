import abc
import typing as t

if t.TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Codec", "Negotiator"]


Input = t.TypeVar("Input")
Output = t.TypeVar("Output")


class Codec(t.Generic[Input, Output], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def decode(self, item: Input, **options) -> Output: ...


C = t.TypeVar("C", bound=Codec)


class Negotiator(t.Generic[C]):
    def __init__(self, codecs: "Sequence[C] | None" = None):
        self.codecs = codecs or []

    @abc.abstractmethod
    def negotiate(self, value: str | None = None, /) -> C: ...
