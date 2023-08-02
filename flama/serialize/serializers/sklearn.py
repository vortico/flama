import codecs
import logging
import math
import pickle
import sys
import typing as t
import warnings

from flama import types
from flama.serialize.base import Serializer
from flama.serialize.types import Framework

if sys.version_info < (3, 8):  # PORT: Remove when stop supporting 3.7 # pragma: no cover
    import importlib

    import importlib_metadata

    importlib.metadata = importlib_metadata
else:
    import importlib.metadata

logger = logging.getLogger(__name__)


class SKLearnSerializer(Serializer):
    lib = Framework.sklearn

    def dump(self, obj: t.Any, **kwargs) -> bytes:
        return codecs.encode(pickle.dumps(obj), "base64")

    def load(self, model: bytes, **kwargs) -> t.Any:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = pickle.loads(codecs.decode(model, "base64"))

        return model

    def _info(self, data) -> types.JSONField:
        if isinstance(data, (int, bool, str)):
            return data

        if isinstance(data, float):
            return None if math.isnan(data) else data

        if isinstance(data, dict):
            return {k: self._info(v) for k, v in data.items()}

        if isinstance(data, (list, tuple, set)):
            return [self._info(i) for i in data]

        return None

    def info(self, model: t.Any) -> t.Optional[types.JSONSchema]:
        try:
            return self._info(model.get_params())  # type: ignore
        except:  # noqa
            logger.exception("Cannot collect info from model")
            return None

    def version(self) -> str:
        return importlib.metadata.version("scikit-learn")
