import datetime
import os
import typing as t
import uuid

from flama.serialize.data_structures import Compression, ModelArtifact

if t.TYPE_CHECKING:
    from flama.serialize.data_structures import Artifacts

__all__ = ["dump"]


def dump(
    model: t.Any,
    path: t.Union[str, os.PathLike],
    *,
    compression: t.Union[str, Compression] = Compression.standard,
    model_id: t.Optional[t.Union[str, uuid.UUID]] = None,
    timestamp: t.Optional[datetime.datetime] = None,
    params: t.Optional[dict[str, t.Any]] = None,
    metrics: t.Optional[dict[str, t.Any]] = None,
    extra: t.Optional[dict[str, t.Any]] = None,
    artifacts: t.Optional["Artifacts"] = None,
    **kwargs,
) -> None:
    """Serialize an ML model using Flama format to bytes stream.

    :param model: The ML model.
    :param path: Model file path.
    :param compression: Compression type.
    :param model_id: The model ID.
    :param timestamp: The model timestamp.
    :param params: The model parameters.
    :param metrics: The model metrics.
    :param extra: The model extra data.
    :param artifacts: The model artifacts.
    :param kwargs: Keyword arguments passed to library dump method.
    """
    ModelArtifact.from_model(
        model,
        model_id=model_id,
        timestamp=timestamp,
        params=params,
        metrics=metrics,
        extra=extra,
        artifacts=artifacts,
    ).dump(path, compression, **kwargs)
