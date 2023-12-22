import codecs
import importlib.metadata
import io
import json
import tarfile
import typing as t
from tempfile import TemporaryDirectory

from flama.serialize import exceptions, types
from flama.serialize.base import Serializer

try:
    import tensorflow as tf  # type: ignore
except Exception:  # pragma: no cover
    tf = None  # type: ignore[misc, assignment]

if t.TYPE_CHECKING:
    from flama.types import JSONSchema


class TensorFlowSerializer(Serializer):
    lib = types.Framework.tensorflow

    def dump(self, obj: t.Any, **kwargs) -> bytes:
        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        buffer = io.BytesIO()
        with TemporaryDirectory() as saved_model_dir, tarfile.open(fileobj=buffer, mode="w") as model_tar:
            tf.keras.models.save_model(obj, saved_model_dir)  # type: ignore
            model_tar.add(saved_model_dir, arcname="")
        buffer.seek(0)
        return codecs.encode(buffer.read(), "base64")

    def load(self, model: bytes, **kwargs) -> t.Any:
        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        with TemporaryDirectory() as saved_model_dir, tarfile.open(
            fileobj=io.BytesIO(codecs.decode(model, "base64")), mode="r:"
        ) as model_tar:
            model_tar.extractall(saved_model_dir)
            return tf.keras.models.load_model(saved_model_dir)  # type: ignore

    def info(self, model: t.Any) -> t.Optional["JSONSchema"]:
        model_info: "JSONSchema" = json.loads(model.to_json())
        return model_info

    def version(self) -> str:
        for lib in ("tensorflow", "tensorflow-cpu", "tensorflow-gpu", "keras"):
            try:
                return importlib.metadata.version(lib)
            except Exception:
                pass

        raise exceptions.FrameworkNotInstalled("tensorflow")  # noqa
