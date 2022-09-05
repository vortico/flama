import typing

from flama.serialize.types import Model, ModelFormat


def dumps(lib: typing.Union[str, ModelFormat], model: typing.Any) -> bytes:
    return Model(ModelFormat(lib), model).to_bytes()


def dump(lib: typing.Union[str, ModelFormat], model: typing.Any, fs: typing.BinaryIO) -> None:
    fs.write(dumps(lib, model))
