import codecs
import importlib.metadata
import io
import typing as t
import warnings

from flama import exceptions, types
from flama.serialize.model_serializers.base import BaseModelSerializer

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # ty: ignore[invalid-assignment]

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

__all__ = ["ModelSerializer"]


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.MLLib] = "torch"

    def dump(
        self,
        obj: t.Any,
        /,
        *,
        example_inputs: tuple[t.Any, ...] | None = None,
        dynamic_shapes: dict[str, t.Any] | None = None,
        **kwargs,
    ) -> bytes:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        if example_inputs is None:
            for m in obj.modules():
                if isinstance(m, torch.nn.Linear):
                    example_inputs = (torch.randn(2, m.in_features),)
                    break
            else:
                raise ValueError("Cannot infer example_inputs; pass them explicitly")

        if dynamic_shapes is None:
            dynamic_shapes = {"x": {0: torch.export.Dim("batch", min=1)}}

        ep = torch.export.export(obj, example_inputs, dynamic_shapes=dynamic_shapes)
        buffer = io.BytesIO()
        torch.export.save(ep, buffer)
        return codecs.encode(buffer.getvalue(), "base64")

    def load(self, model: bytes, /, **kwargs) -> t.Any:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*non-writable.*", category=UserWarning)
            return torch.export.load(io.BytesIO(codecs.decode(model, "base64"))).module()

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
