import codecs
import io
import json
import sys
import tarfile
import typing as t
from tempfile import TemporaryDirectory

from flama.serialize.base import Serializer
from flama.serialize.types import Framework

if sys.version_info < (3, 8):  # PORT: Remove when stop supporting 3.7 # pragma: no cover
    import importlib

    import importlib_metadata

    importlib.metadata = importlib_metadata
else:
    import importlib.metadata

try:
    import tensorflow as tf
except Exception:  # pragma: no cover
    tf = None  # type: ignore[misc, assignment]


class TensorFlowSerializer(Serializer):
    lib = Framework.tensorflow

    def dump(self, obj: t.Any, **kwargs) -> bytes:
        assert tf is not None, "`tensorflow` must be installed to use TensorFlowSerializer."
        buffer = io.BytesIO()
        with TemporaryDirectory() as saved_model_dir, tarfile.open(fileobj=buffer, mode="w") as model_tar:
            tf.keras.models.save_model(obj, saved_model_dir)
            model_tar.add(saved_model_dir, arcname="")
        buffer.seek(0)
        return codecs.encode(buffer.read(), "base64")

    def load(self, model: bytes, **kwargs) -> t.Any:
        assert tf is not None, "`tensorflow` must be installed to use TensorFlowSerializer."
        with TemporaryDirectory() as saved_model_dir, tarfile.open(
            fileobj=io.BytesIO(codecs.decode(model, "base64")), mode="r:"
        ) as model_tar:
            model_tar.extractall(saved_model_dir)
            return tf.keras.models.load_model(saved_model_dir)

    def info(self, model: t.Any) -> t.Dict[str, t.Any]:
        model_info: t.Dict[str, t.Any] = json.loads(model.to_json())
        return model_info

    def version(self) -> str:  # type: ignore[return]
        for lib in ("tensorflow", "tensorflow-cpu", "tensorflow-gpu", "keras"):
            try:
                return importlib.metadata.version(lib)
            except Exception:
                pass
