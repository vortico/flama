import codecs
import importlib.metadata
import json
import tempfile
import typing as t

from flama import exceptions, types
from flama.serialize.model_serializers.base import BaseModelSerializer

try:
    import tensorflow as tf  # type: ignore
except Exception:  # pragma: no cover
    tf = None  # type: ignore[misc, assignment]

if t.TYPE_CHECKING:
    from flama.types import JSONSchema


__all__ = ["ModelSerializer"]


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.MLLib] = "tensorflow"

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        with tempfile.NamedTemporaryFile(mode="rb", suffix=".keras") as tmp_file:
            tf.keras.models.save_model(obj, tmp_file.name)  # type: ignore
            return codecs.encode(tmp_file.read(), "base64")

    def load(self, model: bytes, /, **kwargs) -> t.Any:
        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".keras") as tmp_file:
            tmp_file.write(codecs.decode(model, "base64"))
            return tf.keras.models.load_model(tmp_file.name)  # type: ignore

    def info(self, model: t.Any, /) -> "JSONSchema | None":
        model_info: JSONSchema = json.loads(model.to_json())
        return model_info

    def version(self) -> str:
        for lib in ("tensorflow", "tensorflow-cpu", "tensorflow-gpu", "keras"):
            try:
                return importlib.metadata.version(lib)
            except Exception:  # pragma: no cover
                pass

        raise exceptions.FrameworkNotInstalled("tensorflow")  # noqa
