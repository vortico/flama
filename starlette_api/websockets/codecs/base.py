import typing

from starlette_api.websockets.types import Message


class Codec:
    encoding = None

    async def decode(self, message: Message, **options):
        raise NotImplementedError()

    async def encode(self, item: typing.Any, **options):
        raise NotImplementedError()
