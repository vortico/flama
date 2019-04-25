import typing

from flama import http, websockets


class Codec:
    async def decode(self, item: typing.Any, **options):
        raise NotImplementedError()

    async def encode(self, item: typing.Any, **options):
        raise NotImplementedError()


class HTTPCodec(Codec):
    media_type = None

    async def decode(self, request: http.Request, **options):
        raise NotImplementedError()

    async def encode(self, item: typing.Any, **options):
        raise NotImplementedError()


class WebsocketsCodec(Codec):
    encoding = None

    async def decode(self, item: websockets.Message, **options):
        raise NotImplementedError()

    async def encode(self, item: typing.Any, **options):
        raise NotImplementedError()
