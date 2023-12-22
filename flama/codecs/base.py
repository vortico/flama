import abc
import typing as t

if t.TYPE_CHECKING:
    from flama import http, types


class Codec(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def decode(self, item: t.Any, **options) -> t.Any:
        ...


class HTTPCodec(Codec):
    media_type: t.Optional[str] = None

    @abc.abstractmethod
    async def decode(self, item: "http.Request", **options) -> t.Any:
        ...


class WebsocketsCodec(Codec):
    encoding: t.Optional[str] = None

    @abc.abstractmethod
    async def decode(self, item: "types.Message", **options) -> t.Any:
        ...
