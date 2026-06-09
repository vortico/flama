import dataclasses
import typing as t

from flama import compat, types
from flama.models.engine.llm.input import EngineInput
from flama.models.transport.input.llm.shape.base import Shape, _ShapeFields, _ShapeRenderKwargs

if t.TYPE_CHECKING:
    from flama.models.engine.backend.llm.base import LLMBackend

__all__ = ["Raw"]


@dataclasses.dataclass(frozen=True)
class Raw(Shape):
    """Untemplated input. The prompt is sent verbatim to the engine.

    The tokenizer adds the BOS token via its default ``add_special_tokens=True``; no chat template
    is applied. :meth:`render` accepts the marker :class:`_ShapeRenderKwargs` shape for API
    parity with the templated variants but consumes none of its fields.

    :param prompt: Raw prompt text.
    """

    prompt: str = dataclasses.field(init=False)
    fields: dataclasses.InitVar[_ShapeFields | None] = None
    transport: t.ClassVar[types.LLMTransportShape] = "raw"

    def __post_init__(self, fields: _ShapeFields | None) -> None:
        super().__post_init__(fields)
        if (prompt := (fields or {}).get("prompt")) is None:
            raise ValueError("'prompt' is required when transport is 'raw'")

        object.__setattr__(self, "prompt", prompt)

    async def render(self, backend: "LLMBackend", /, **kwargs: compat.Unpack[_ShapeRenderKwargs]) -> EngineInput:
        return EngineInput(tokens=list(backend.encode(self.prompt, add_special_tokens=True)))
