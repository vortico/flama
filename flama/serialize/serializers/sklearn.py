import codecs
import math
import pickle
import sys
import typing as t
import warnings

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
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = pickle.loads(codecs.decode(model, "base64"))

        return model

    def _info(self, data):
        if isinstance(data, (int, bool, str)):
            return data

        if isinstance(data, float):
            return None if math.isnan(data) else data

        if isinstance(data, dict):
            return {k: self._info(v) for k, v in data.items()}

        if isinstance(data, (list, tuple, set)):
            return [self._info(i) for i in data]

        try:
            return self._info(data.get_params())
        except:  # noqa
            return None

    def info(self, model: t.Any) -> t.Dict[str, t.Any]:
        model_info: t.Dict[str, t.Any] = self._info(model)
        return model_info

    def version(self) -> str:
        return importlib.metadata.version("scikit-learn")
