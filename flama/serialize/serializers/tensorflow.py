import codecs
import pickle
import typing

from flama.serialize.base import Serializer


class TensorflowSerializer(Serializer):
    def dump(self, obj: typing.Any) -> bytes:
        return codecs.encode(pickle.dumps(obj), "base64")

    def load(self, model: bytes) -> typing.Any:
        return pickle.loads(codecs.decode(model, "base64"))
