import codecs
import importlib.metadata
import json
import typing as t

from flama import exceptions, types
from flama.serialize.model_serializers.base import BaseModelSerializer

try:
    import transformers
except Exception:  # pragma: no cover
    transformers = None  # ty: ignore[invalid-assignment]

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

__all__ = ["ModelSerializer"]


class _TransformersModel:
    """Lightweight wrapper to bundle a transformers model and its tokenizer as a single object."""

    def __init__(self, model: t.Any, tokenizer: t.Any, model_id: str) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.model_id = model_id


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.MLLib] = "transformers"

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        model_id: str | None = None

        if isinstance(obj, _TransformersModel):
            model_id = obj.model_id
        elif hasattr(obj, "name_or_path"):
            model_id = obj.name_or_path

        if not model_id:
            raise ValueError("Cannot determine model identifier from the given model object")

        return codecs.encode(json.dumps({"model_id": model_id}).encode(), "base64")

    def load(self, model: bytes, /, **kwargs) -> t.Any:
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        data = json.loads(codecs.decode(model, "base64").decode())
        return self.load_from_id(data["model_id"], **kwargs)

    def load_from_id(self, model_id: str, /, **kwargs) -> _TransformersModel:
        """Load a transformers model and tokenizer directly from a model identifier.

        :param model_id: HuggingFace model identifier or local path.
        :param kwargs: Additional keyword arguments passed to ``from_pretrained``.
        :return: A composite object carrying the model and tokenizer.
        """
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        model = transformers.AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
        tokenizer = transformers.AutoTokenizer.from_pretrained(model_id, **kwargs)

        if tokenizer is None:
            raise ValueError(f"Failed to load tokenizer for model '{model_id}'")

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        return _TransformersModel(model=model, tokenizer=tokenizer, model_id=model_id)

    def info(self, model: t.Any, /) -> "JSONSchema | None":
        obj = model.model if isinstance(model, _TransformersModel) else model

        if hasattr(obj, "config"):
            return obj.config.to_dict()

        return None

    def version(self) -> str:
        try:
            return importlib.metadata.version("transformers")
        except Exception:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")
