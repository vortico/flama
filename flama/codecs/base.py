import abc
import typing

from flama import http, websockets


class Codec(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def decode(self, item: typing.Any, **options):
        ...

    @abc.abstractmethod
    async def encode(self, item: typing.Any, **options):
        ...


class HTTPCodec(Codec):
    media_type = None

    async def decode(self, request: http.Request, **options):
        ...

    async def encode(self, item: typing.Any, **options):
        ...


class WebsocketsCodec(Codec):
    encoding = None

    async def decode(self, message: websockets.Message, **options):
        ...

    async def encode(self, item: typing.Any, **options):
        ...
