import dataclasses
import typing as t

from flama import compat, types
from flama.models.transport.input.llm.message import Message, SystemMessage, TextContent, UserMessage
from flama.models.transport.input.llm.shape.base import Shape, _ShapeFields, _ShapeRenderKwargs
from flama.models.transport.input.llm.tool import Tool

if t.TYPE_CHECKING:
    from flama.models.engine.backend.llm.base import LLMBackend
from flama.models.engine.llm.input import EngineInput

__all__ = ["Chat"]


@dataclasses.dataclass(frozen=True)
class Chat(Shape):
    """Single-turn chat input with an optional system instruction.

    The backend's chat template is applied to ``[system?, user(prompt)]`` to produce the engine
    input. When ``tools`` is provided, the tuple is forwarded to the chat template so the model
    sees the available function specs. :meth:`render` consumes
    :attr:`_ShapeRenderKwargs.chat_template_kwargs` and forwards it to
    :meth:`~flama.models.engine.backend.llm.base.LLMBackend.prepare_input`.

    :param prompt: User turn content.
    :param system: Optional system instruction prepended as a system role message.
    :param tools: Optional tuple of canonical L2 :class:`Tool` specs advertised to the model.
    """

    prompt: str = dataclasses.field(init=False)
    system: str | None = dataclasses.field(init=False, default=None)
    tools: tuple[Tool, ...] | None = dataclasses.field(init=False, default=None)
    fields: dataclasses.InitVar[_ShapeFields | None] = None
    transport: t.ClassVar[types.LLMTransportShape] = "chat"

    def __post_init__(self, fields: _ShapeFields | None) -> None:
        super().__post_init__(fields)
        bag = fields or {}
        prompt = bag.get("prompt")
        if prompt is None:
            raise ValueError("'prompt' is required when transport is 'chat'")
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "system", bag.get("system"))
        object.__setattr__(self, "tools", bag.get("tools"))

    async def render(self, backend: "LLMBackend", /, **kwargs: compat.Unpack[_ShapeRenderKwargs]) -> "EngineInput":
        if backend.chat_template is None:
            raise ValueError("Model has no chat template, use transport='raw'")

        messages: list[Message] = []
        if self.system is not None:
            messages.append(SystemMessage(content=(TextContent(text=self.system),)))
        messages.append(UserMessage(content=(TextContent(text=self.prompt),)))

        return await backend.prepare_input(
            messages,
            tools=self.tools,
            chat_template_kwargs=kwargs.get("chat_template_kwargs"),
        )
