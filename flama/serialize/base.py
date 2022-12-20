import abc
import typing as t

from flama.serialize.types import Framework

__all__ = ["Serializer"]


class Serializer(metaclass=abc.ABCMeta):
    lib: t.ClassVar[Framework]

    @abc.abstractmethod
    def dump(self, obj: t.Any, **kwargs) -> bytes:
        ...

    @abc.abstractmethod
    def load(self, model: bytes, **kwargs) -> t.Any:
        ...

    @abc.abstractmethod
    def info(self, model: t.Any) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def version(self) -> str:
        ...
