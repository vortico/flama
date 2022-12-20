import codecs
import io
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
