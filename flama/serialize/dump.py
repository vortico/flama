import datetime
import typing as t
import uuid

from flama.serialize.data_structures import ModelArtifact


def dumps(
    model: t.Any,
    *,
    model_id: t.Optional[t.Union[str, uuid.UUID]] = None,
    timestamp: t.Optional[datetime.datetime] = None,
    params: t.Optional[t.Dict[str, t.Any]] = None,
    metrics: t.Optional[t.Dict[str, t.Any]] = None,
    extra: t.Optional[t.Dict[str, t.Any]] = None,
    **kwargs
) -> bytes:
    """Serialize a ML model using Flama format to bytes string.

    :param model: The ML model.
    :param model_id: The model ID.
    :param timestamp: The model timestamp.
    :param params: The model parameters.
    :param metrics: The model metrics.
    :param extra: The model extra data.
    :param kwargs: Keyword arguments passed to library dump method.
    :return: Serialized model using Flama format.
    """
    return ModelArtifact.from_model(
        model, model_id=model_id, timestamp=timestamp, params=params, metrics=metrics, extra=extra
    ).to_bytes(**kwargs)


def dump(
    model: t.Any,
    fs: t.BinaryIO,
    *,
    model_id: t.Optional[t.Union[str, uuid.UUID]] = None,
    timestamp: t.Optional[datetime.datetime] = None,
    params: t.Optional[t.Dict[str, t.Any]] = None,
    metrics: t.Optional[t.Dict[str, t.Any]] = None,
    extra: t.Optional[t.Dict[str, t.Any]] = None,
    **kwargs
) -> None:
    """Serialize a ML model using Flama format to bytes stream.

    :param model: The ML model.
    :param model_id: The model ID.
    :param timestamp: The model timestamp.
    :param params: The model parameters.
    :param metrics: The model metrics.
    :param extra: The model extra data.
    :param fs: Output bytes stream.
    :param kwargs: Keyword arguments passed to library dump method.
    :return: Serialized model using Flama format.
    """
    fs.write(
        dumps(model, model_id=model_id, timestamp=timestamp, params=params, metrics=metrics, extra=extra, **kwargs)
    )
