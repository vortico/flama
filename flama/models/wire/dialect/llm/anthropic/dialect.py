import typing as t
import uuid

from flama import compat
from flama.http.responses.sse import ServerSentEvent
from flama.models.wire.dialect.base import Dialect
from flama.models.wire.dialect.llm.anthropic.assembler import AnthropicAssembleKwargs, AnthropicAssembler
from flama.models.wire.dialect.llm.anthropic.parser import AnthropicParser
from flama.models.wire.dialect.llm.anthropic.renderer import AnthropicRenderer

__all__ = ["AnthropicDialect", "AnthropicRenderKwargs"]


class AnthropicRenderKwargs(t.TypedDict, total=False):
    """Per-stream kwargs accepted by :meth:`AnthropicDialect.render`.

    Mirrors the constructor signature of
    :class:`~flama.models.wire.dialect.llm.anthropic.AnthropicRenderer` exactly so :meth:`Dialect.render`
    can forward ``**kwargs`` directly.
    """

    model: compat.Required[str]
    generation_id: uuid.UUID | None


class AnthropicDialect(Dialect[ServerSentEvent, AnthropicRenderKwargs, AnthropicAssembleKwargs]):
    """Anthropic-compatible wire dialect.

    Binds three strategies that drive the :class:`~flama.models.wire.dialect.base.Dialect` façade:

    - :attr:`PARSER` -> :class:`~flama.models.wire.dialect.llm.anthropic.AnthropicParser` (L1 -> L2 input).
    - :attr:`RENDERER` -> :class:`~flama.models.wire.dialect.llm.anthropic.AnthropicRenderer` (L2 -> L1
      streaming).
    - :attr:`ASSEMBLER` -> :class:`~flama.models.wire.dialect.llm.anthropic.AnthropicAssembler` (L2 -> L1
      buffered Messages envelope).
    """

    PARSER = AnthropicParser
    RENDERER = AnthropicRenderer
    ASSEMBLER = AnthropicAssembler
