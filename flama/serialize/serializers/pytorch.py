import codecs
import importlib.metadata
import io
import typing as t

from flama import exceptions
from flama.serialize import types
from flama.serialize.base import Serializer

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore[misc, assignment]

if t.TYPE_CHECKING:
    from flama.types import JSONSchema


class PyTorchSerializer(Serializer):
    lib = types.Framework.torch

    def dump(self, obj: t.Any, **kwargs) -> bytes:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        buffer = io.BytesIO()
        torch.jit.save(torch.jit.script(obj), buffer, **kwargs)
        buffer.seek(0)
        return codecs.encode(buffer.read(), "base64")

    def load(self, model: bytes, **kwargs) -> t.Any:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        return torch.jit.load(io.BytesIO(codecs.decode(model, "base64")), **kwargs)

    def info(self, model: t.Any) -> t.Optional["JSONSchema"]:
        return {
            "modules": [str(x) for x in model.modules()],
            "parameters": {k: str(v) for k, v in model.named_parameters()},
            "state": {k: v.tolist() if hasattr(v, "tolist") else v for k, v in model.state_dict().items()},
        }

    def version(self) -> str:
        try:
            return importlib.metadata.version("torch")
        except Exception:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")
