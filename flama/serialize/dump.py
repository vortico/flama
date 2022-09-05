import typing

from flama.serialize.types import Model, ModelFormat


def dumps(lib: typing.Union[str, ModelFormat], model: typing.Any) -> bytes:
    """Serialize a ML model using Flama format to bytes string.

    :param lib: The ML library used for building the model.
    :param model: The ML model.
    :return: Serialized model using Flama format.
    """
    return Model(ModelFormat(lib), model).to_bytes()


def dump(lib: typing.Union[str, ModelFormat], model: typing.Any, fs: typing.BinaryIO) -> None:
    """Serialize a ML model using Flama format to bytes stream.

    :param lib: The ML library used for building the model.
    :param model: The ML model.
    :param fs: Output bytes stream.
    :return: Serialized model using Flama format.
    """
    fs.write(dumps(lib, model))
