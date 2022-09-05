import typing

from flama.serialize.types import Model


def loads(data: bytes) -> Model:
    """Deserialize a ML model using Flama format from a bytes string.

    :param data: The serialized model.
    :return: ML model.
    """
    return Model.from_bytes(data)


def load(fs: typing.BinaryIO) -> Model:
    """Deserialize a ML model using Flama format from a bytes stream.

    :param fs: Input bytes stream containing the serialized model.
    :return: ML model.
    """
    return loads(fs.read())
