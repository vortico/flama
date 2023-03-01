import os
import typing as t

from flama.serialize.data_structures import ModelArtifact

__all__ = ["load"]


def load(path: t.Union[str, os.PathLike], **kwargs) -> ModelArtifact:
    """Deserialize a ML model using Flama format from a bytes stream.

    :param path: Model file path.
    :param kwargs: Keyword arguments passed to library load method.
    :return: Model artifact.
    """
    return ModelArtifact.load(path, **kwargs)
