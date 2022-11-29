import codecs
import io
import tarfile
import typing
from tempfile import TemporaryDirectory

from flama.serialize.base import Serializer

try:
    import tensorflow as tf
except Exception:  # pragma: no cover
    tf = None  # type: ignore[misc, assignment]


class TensorFlowSerializer(Serializer):
    def dump(self, obj: typing.Any, **kwargs) -> bytes:
        assert tf is not None, "`tensorflow` must be installed to use TensorFlowSerializer."
        buffer = io.BytesIO()
        with TemporaryDirectory() as saved_model_dir, tarfile.open(fileobj=buffer, mode="w") as model_tar:
            tf.keras.models.save_model(obj, saved_model_dir)
            model_tar.add(saved_model_dir, arcname="")
            model_tar.list()
        buffer.seek(0)
        return codecs.encode(buffer.read(), "base64")

    def load(self, model: bytes, **kwargs) -> typing.Any:
        assert tf is not None, "`tensorflow` must be installed to use TensorFlowSerializer."
        with TemporaryDirectory() as saved_model_dir, tarfile.open(
            fileobj=io.BytesIO(codecs.decode(model, "base64")), mode="r:"
        ) as model_tar:
            model_tar.extractall(saved_model_dir)
            return tf.keras.models.load_model(saved_model_dir)
