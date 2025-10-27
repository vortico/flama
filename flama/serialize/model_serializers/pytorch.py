import codecs
import importlib.metadata
import io
import typing as t

from flama import exceptions, types
from flama.serialize.model_serializers.base import BaseModelSerializer

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore[misc, assignment]

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

__all__ = ["ModelSerializer"]


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.MLLib] = "torch"

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        buffer = io.BytesIO()
        torch.jit.save(torch.jit.script(obj), buffer, **kwargs)
        buffer.seek(0)
        return codecs.encode(buffer.read(), "base64")

    def load(self, model: bytes, /, **kwargs) -> t.Any:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        return torch.jit.load(io.BytesIO(codecs.decode(model, "base64")), **kwargs)

    def info(self, model: t.Any, /) -> "JSONSchema | None":
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
