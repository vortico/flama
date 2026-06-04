import codecs
import importlib.metadata
import logging
import math
import pathlib
import pickle
import typing as t
import warnings

from flama import exceptions, types
from flama.serialize.data_structures import MLModelCapabilities
from flama.serialize.model_serializers.base import BaseModelSerializer

if t.TYPE_CHECKING:
    from flama.types import JSONField, JSONSchema

logger = logging.getLogger(__name__)


__all__ = ["ModelSerializer"]


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.ModelLib] = "sklearn"

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        return codecs.encode(pickle.dumps(obj), "base64")

    def load(self, source: bytes | pathlib.Path, /, **kwargs) -> t.Any:
        if isinstance(source, pathlib.Path):
            raise TypeError("sklearn serializer expects raw bytes, not a directory path")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return pickle.loads(codecs.decode(source, "base64"))

    def _info(self, data, /) -> "JSONField":
        if isinstance(data, int | bool | str):
            return data

        if isinstance(data, float):
            return None if math.isnan(data) else data

        if isinstance(data, dict):
            return {k: self._info(v) for k, v in data.items()}

        if isinstance(data, list | tuple | set):
            return [self._info(i) for i in data]

        return None

    def info(self, model: t.Any) -> "JSONSchema | None":
        try:
            return self._info(model.get_params())  # type: ignore
        except:  # noqa
            logger.exception("Cannot collect info from model")
            return None

    def detect_capabilities(self, model: t.Any, /) -> MLModelCapabilities:
        """Return the empty :class:`MLModelCapabilities` placeholder for traditional ML artifacts."""
        return MLModelCapabilities()

    def version(self) -> str:
        try:
            return importlib.metadata.version("scikit-learn")
        except Exception:  # noqa
            raise exceptions.FrameworkNotInstalled("scikit-learn")
