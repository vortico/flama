import abc
import typing

__all__ = ["Serializer"]


class Serializer(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def dump(self, obj: typing.Any) -> bytes:
        ...

    @abc.abstractmethod
    def load(self, model: bytes) -> typing.Any:
        ...
