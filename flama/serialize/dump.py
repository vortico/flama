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
    path: str | os.PathLike,
    *,
    compression: str | Compression = Compression.standard,
    model_id: str | uuid.UUID | None = None,
    timestamp: datetime.datetime | None = None,
    params: dict[str, t.Any] | None = None,
    metrics: dict[str, t.Any] | None = None,
    extra: dict[str, t.Any] | None = None,
    artifacts: "Artifacts | None" = None,
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
