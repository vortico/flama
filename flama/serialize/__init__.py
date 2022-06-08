import typing

from flama.serialize.types import Format, Model

__all__ = ["dump", "dumps", "load", "loads"]


def dumps(lib: typing.Union[str, Format], model: typing.Any) -> bytes:
    return Model(Format(lib), model).to_bytes()


def dump(lib: typing.Union[str, Format], model: typing.Any, fs: typing.BinaryIO) -> None:
    fs.write(dumps(lib, model))


def loads(data: bytes) -> Model:
    return Model.from_bytes(data)


def load(fs: typing.BinaryIO) -> Model:
    return loads(fs.read())
