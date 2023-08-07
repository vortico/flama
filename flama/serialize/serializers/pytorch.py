import codecs
import importlib.metadata
import io
import typing as t

from flama.serialize.base import Serializer
from flama.serialize.types import Framework

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore[misc, assignment]


class PyTorchSerializer(Serializer):
    lib = Framework.torch

    def dump(self, obj: t.Any, **kwargs) -> bytes:
        assert torch is not None, "`pytorch` must be installed to use PyTorchSerializer."
        buffer = io.BytesIO()
        torch.jit.save(torch.jit.script(obj), buffer, **kwargs)
        buffer.seek(0)
        return codecs.encode(buffer.read(), "base64")

    def load(self, model: bytes, **kwargs) -> t.Any:
        assert torch is not None, "`pytorch` must be installed to use PyTorchSerializer."
        return torch.jit.load(io.BytesIO(codecs.decode(model, "base64")), **kwargs)

    def info(self, model: t.Any) -> t.Dict[str, t.Any]:
        return {
            "modules": [str(x) for x in model.modules()],
            "parameters": {k: str(v) for k, v in model.named_parameters()},
            "state": {k: v.tolist() if hasattr(v, "tolist") else v for k, v in model.state_dict().items()},
        }

    def version(self) -> str:
        return importlib.metadata.version("torch")
