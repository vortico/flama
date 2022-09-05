import typing

from flama.serialize.types import Model


def loads(data: bytes) -> Model:
    return Model.from_bytes(data)


def load(fs: typing.BinaryIO) -> Model:
    return loads(fs.read())
