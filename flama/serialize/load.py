import typing

from flama.serialize.data_structures import ModelArtifact


def loads(data: bytes, **kwargs) -> ModelArtifact:
    """Deserialize a ML model using Flama format from a bytes string.

    :param data: The serialized model.
    :param kwargs: Keyword arguments passed to library load method.
    :return: ML model.
    """
    return ModelArtifact.from_bytes(data, **kwargs)


def load(fs: typing.BinaryIO, **kwargs) -> ModelArtifact:
    """Deserialize a ML model using Flama format from a bytes stream.

    :param fs: Input bytes stream containing the serialized model.
    :param kwargs: Keyword arguments passed to library load method.
    :return: ML model.
    """
    return loads(fs.read(), **kwargs)
