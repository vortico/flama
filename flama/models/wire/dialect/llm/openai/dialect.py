import typing as t
import uuid

from flama import compat
from flama.http.responses.sse import ServerSentEvent
from flama.models.wire.dialect.base import Dialect
from flama.models.wire.dialect.llm.openai.assembler import OpenAIAssembleKwargs, OpenAIAssembler
from flama.models.wire.dialect.llm.openai.parser import OpenAIParser
from flama.models.wire.dialect.llm.openai.renderer import OpenAIRenderer

__all__ = ["OpenAIDialect", "OpenAIRenderKwargs"]


class OpenAIRenderKwargs(t.TypedDict, total=False):
    """Per-stream kwargs accepted by :meth:`OpenAIDialect.render`.

    Mirrors the constructor signature of
    :class:`~flama.models.wire.dialect.llm.openai.OpenAIRenderer` exactly so :meth:`Dialect.render` can
    forward ``**kwargs`` directly.
    """

    api: compat.Required[t.Literal["chat", "completion", "response"]]
    model: compat.Required[str]
    generation_id: uuid.UUID | None


class OpenAIDialect(Dialect[ServerSentEvent, OpenAIRenderKwargs, OpenAIAssembleKwargs]):
    """OpenAI-compatible wire dialect.

    Binds three strategies that drive the :class:`~flama.models.wire.dialect.base.Dialect` façade:

    - :attr:`PARSER` -> :class:`~flama.models.wire.dialect.llm.openai.OpenAIParser` (L1 -> L2 input).
    - :attr:`RENDERER` -> :class:`~flama.models.wire.dialect.llm.openai.OpenAIRenderer` (L2 -> L1 streaming).
    - :attr:`ASSEMBLER` -> :class:`~flama.models.wire.dialect.llm.openai.OpenAIAssembler` (L2 -> L1 buffered).

    The renderer dispatches internally on ``api`` between chat-completions / completions chunks and the
    Responses API event shape; the assembler dispatches on the same discriminator between the
    ``chat.completion`` / ``text_completion`` / ``response`` buffered envelope shapes.
    """

    PARSER = OpenAIParser
    RENDERER = OpenAIRenderer
    ASSEMBLER = OpenAIAssembler
