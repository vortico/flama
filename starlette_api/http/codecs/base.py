import typing


class Codec:
    media_type = None

    async def decode(self, bytestring: bytes, **options):
        raise NotImplementedError()

    async def encode(self, item: typing.Any, **options):
        raise NotImplementedError()
