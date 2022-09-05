import codecs
import dataclasses
import enum
import json
import typing

from flama.serialize.base import Serializer
from flama.serialize.serializers.pytorch import PyTorchSerializer
from flama.serialize.serializers.sklearn import SKLearnSerializer
from flama.serialize.serializers.tensorflow import TensorFlowSerializer


class ModelFormat(enum.Enum):
    sklearn = "sklearn"
    tensorflow = "tensorflow"
    pytorch = "pytorch"


SERIALIZERS = {
    ModelFormat.sklearn: SKLearnSerializer(),
    ModelFormat.tensorflow: TensorFlowSerializer(),
    ModelFormat.pytorch: PyTorchSerializer(),
}


@dataclasses.dataclass(frozen=True)
class Model:
    lib: ModelFormat
    model: typing.Any

    @classmethod
    def serializer(cls, lib: ModelFormat) -> Serializer:
        try:
            return SERIALIZERS[lib]
        except ValueError:
            raise ValueError("Wrong lib")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Model":
        try:
            serialized_data = json.loads(codecs.decode(data, "zlib"))
            lib = ModelFormat(serialized_data["lib"])
            model = cls.serializer(lib).load(serialized_data["model"].encode())
        except KeyError:
            raise ValueError("Wrong data")

        return cls(lib, model)

    def to_dict(self) -> typing.Dict[str, typing.Any]:
        pickled_model = self.serializer(self.lib).dump(self.model).decode()
        return {"lib": self.lib.value, "model": pickled_model}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def to_bytes(self) -> bytes:
        return codecs.encode(self.to_json().encode(), "zlib")
