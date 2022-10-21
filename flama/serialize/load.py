import typing

from flama.serialize.model import Model


def loads(data: bytes, **kwargs) -> Model:
    """Deserialize a ML model using Flama format from a bytes string.

    :param data: The serialized model.
    :param kwargs: Keyword arguments passed to library load method.
    :return: ML model.
    """
    return Model.from_bytes(data, **kwargs)


def load(fs: typing.BinaryIO, **kwargs) -> Model:
    """Deserialize a ML model using Flama format from a bytes stream.

    :param fs: Input bytes stream containing the serialized model.
    :param kwargs: Keyword arguments passed to library load method.
    :return: ML model.
    """
    return loads(fs.read(), **kwargs)
