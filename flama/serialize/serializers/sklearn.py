import codecs
import pickle
import sys
import typing as t

from flama.serialize.base import Serializer
from flama.serialize.types import Framework

if sys.version_info < (3, 8):  # PORT: Remove when stop supporting 3.7 # pragma: no cover
    import importlib

    import importlib_metadata

    importlib.metadata = importlib_metadata
else:
    import importlib.metadata


class SKLearnSerializer(Serializer):
    lib = Framework.sklearn

    def dump(self, obj: t.Any, **kwargs) -> bytes:
        return codecs.encode(pickle.dumps(obj), "base64")

    def load(self, model: bytes, **kwargs) -> t.Any:
        return pickle.loads(codecs.decode(model, "base64"))

    def info(self, model: t.Any) -> t.Dict[str, t.Any]:
        model_info: t.Dict[str, t.Any] = model.get_params()
        return model_info

    def version(self) -> str:
        return importlib.metadata.version("scikit-learn")
