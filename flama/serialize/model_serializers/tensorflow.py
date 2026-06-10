import codecs
import importlib.metadata
import json
import pathlib
import tempfile
import typing as t

from flama import exceptions, types
from flama.serialize.data_structures import MLModelCapabilities
from flama.serialize.model_serializers._base import BaseModelSerializer

try:
    import tensorflow as tf
except Exception:  # pragma: no cover
    tf = None

try:
    import keras.models as keras_models
except Exception:  # pragma: no cover
    keras_models = None

if t.TYPE_CHECKING:
    from flama.types import JSONSchema


__all__ = ["ModelSerializer"]


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.ModelLib] = "tensorflow"

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        if keras_models is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        with tempfile.NamedTemporaryFile(mode="rb", suffix=".keras") as tmp_file:
            keras_models.save_model(obj, tmp_file.name)
            return codecs.encode(tmp_file.read(), "base64")

    def load(self, source: bytes | pathlib.Path, /, **kwargs) -> t.Any:
        if keras_models is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        if isinstance(source, pathlib.Path):
            raise TypeError("tensorflow serializer expects raw bytes, not a directory path")

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".keras") as tmp_file:
            tmp_file.write(codecs.decode(source, "base64"))
            return keras_models.load_model(tmp_file.name)

    def info(self, model: t.Any, /) -> "JSONSchema | None":
        model_info: JSONSchema = json.loads(model.to_json())
        return model_info

    def detect_capabilities(self, model: t.Any, /) -> MLModelCapabilities:
        """Return the empty :class:`MLModelCapabilities` placeholder for traditional ML artifacts."""
        return MLModelCapabilities()

    def version(self) -> str:
        for lib in ("tensorflow", "tensorflow-cpu", "tensorflow-gpu", "keras"):
            try:
                return importlib.metadata.version(lib)
            except Exception:  # pragma: no cover
                pass

        raise exceptions.FrameworkNotInstalled("tensorflow")  # noqa
