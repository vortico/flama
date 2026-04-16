import importlib.metadata
import json
import typing as t

from flama import exceptions, types
from flama.serialize.model_serializers.base import BaseModelSerializer

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

__all__ = ["ModelSerializer"]


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.MLLib] = "transformers"

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        descriptor = {"task": getattr(obj, "task", None)}
        return json.dumps(descriptor).encode()

    def load(self, model: bytes, /, **kwargs) -> t.Any:
        return json.loads(model)

    def info(self, model: t.Any, /) -> "JSONSchema | None":
        try:
            info: dict[str, t.Any] = {}
            if hasattr(model, "model") and hasattr(model.model, "config"):
                info["config"] = model.model.config.to_dict()
            if hasattr(model, "task"):
                info["task"] = model.task
            if hasattr(model, "model") and hasattr(model.model, "name_or_path"):
                info["model_name"] = model.model.name_or_path
            return info or None
        except Exception:  # noqa
            return None

    def version(self) -> str:
        try:
            return importlib.metadata.version("transformers")
        except Exception:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")
