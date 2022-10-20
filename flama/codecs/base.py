import abc
import typing as t

if t.TYPE_CHECKING:
    from flama import http, types


class Codec(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def decode(self, item: t.Any, **options):
        ...

    @abc.abstractmethod
    async def encode(self, item: t.Any, **options):
        ...


class HTTPCodec(Codec):
    media_type: t.Optional[str] = None

    async def decode(self, item: "http.Request", **options):
        ...

    async def encode(self, item: t.Any, **options):
        ...


class WebsocketsCodec(Codec):
    encoding: t.Optional[str] = None

    async def decode(self, item: "types.Message", **options):
        ...

    async def encode(self, item: t.Any, **options):
        ...
