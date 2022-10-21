import typing

from flama.serialize.model import Model, ModelFormat


def dumps(lib: typing.Union[str, ModelFormat], model: typing.Any, **kwargs) -> bytes:
    """Serialize a ML model using Flama format to bytes string.

    :param lib: The ML library used for building the model.
    :param model: The ML model.
    :param kwargs: Keyword arguments passed to library dump method.
    :return: Serialized model using Flama format.
    """
    return Model(ModelFormat(lib), model).to_bytes(**kwargs)


def dump(lib: typing.Union[str, ModelFormat], model: typing.Any, fs: typing.BinaryIO, **kwargs) -> None:
    """Serialize a ML model using Flama format to bytes stream.

    :param lib: The ML library used for building the model.
    :param model: The ML model.
    :param fs: Output bytes stream.
    :param kwargs: Keyword arguments passed to library dump method.
    :return: Serialized model using Flama format.
    """
    fs.write(dumps(lib, model, **kwargs))
