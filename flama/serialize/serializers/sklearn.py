import codecs
import pickle
import typing

from flama.serialize.base import Serializer


class SKLearnSerializer(Serializer):
    def dump(self, obj: typing.Any, **kwargs) -> bytes:
        return codecs.encode(pickle.dumps(obj), "base64")

    def load(self, model: bytes, **kwargs) -> typing.Any:
        return pickle.loads(codecs.decode(model, "base64"))
