import dataclasses
import typing as t

from flama import compat, types
from flama.models.transport.input.llm.message import Message
from flama.models.transport.input.llm.shape.base import Shape, _ShapeFields, _ShapeRenderKwargs
from flama.models.transport.input.llm.tool import Tool

if t.TYPE_CHECKING:
    from flama.models.engine.backend.llm.base import LLMBackend
from flama.models.engine.llm.input import EngineInput

__all__ = ["Conversation"]


@dataclasses.dataclass(frozen=True)
class Conversation(Shape):
    """Multi-turn conversation input.

    The backend's chat template is applied to the full ``messages`` tuple to produce the engine
    input. ``messages`` is required to be an immutable :class:`tuple`; the caller is responsible
    for converting any iterable input. When ``tools`` is provided, the tuple is forwarded to the
    chat template so the model sees the available function specs. :meth:`render` consumes
    :attr:`_ShapeRenderKwargs.chat_template_kwargs` and forwards it to
    :meth:`~flama.models.engine.backend.llm.base.LLMBackend.prepare_input`.

    Multimodal payloads (messages whose ``content`` carries non-text parts) require the
    backend's :attr:`~flama.models.engine.backend.llm.base.LLMBackend.capabilities` to advertise the
    matching modality (``image`` / ``audio``); the per-modality gating happens inside
    :meth:`~flama.models.engine.backend.llm.base.LLMBackend.prepare_input`, which raises
    :class:`~flama.models.exceptions.LLMUnsupportedCapability` so the serving layer can
    surface it as a 400.

    :param messages: Ordered tuple of role-tagged messages forming the conversation history.
    :param tools: Optional tuple of canonical L2 :class:`Tool` specs advertised to the model.
    """

    messages: tuple[Message, ...] = dataclasses.field(init=False)
    tools: tuple[Tool, ...] | None = dataclasses.field(init=False, default=None)
    fields: dataclasses.InitVar[_ShapeFields | None] = None
    transport: t.ClassVar[types.LLMTransportShape] = "conversation"

    def __post_init__(self, fields: _ShapeFields | None) -> None:
        super().__post_init__(fields)
        bag = fields or {}
        messages = bag.get("messages")
        if messages is None:
            raise ValueError("'messages' is required when transport is 'conversation'")
        if not messages:
            raise ValueError("'messages' must be non-empty")
        object.__setattr__(self, "messages", messages)
        object.__setattr__(self, "tools", bag.get("tools"))

    async def render(self, backend: "LLMBackend", /, **kwargs: compat.Unpack[_ShapeRenderKwargs]) -> "EngineInput":
        if backend.chat_template is None:
            raise ValueError("Model has no chat template, use transport='raw'")

        return await backend.prepare_input(
            self.messages,
            tools=self.tools,
            chat_template_kwargs=kwargs.get("chat_template_kwargs"),
        )
