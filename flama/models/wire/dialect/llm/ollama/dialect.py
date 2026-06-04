import typing as t

from flama import compat, types
from flama.models.wire.dialect.base import Dialect
from flama.models.wire.dialect.llm.ollama.assembler import OllamaAssembleKwargs, OllamaAssembler
from flama.models.wire.dialect.llm.ollama.parser import OllamaParser
from flama.models.wire.dialect.llm.ollama.renderer import OllamaRenderer

__all__ = ["OllamaDialect", "OllamaRenderKwargs"]


class OllamaRenderKwargs(t.TypedDict, total=False):
    """Per-stream kwargs accepted by :meth:`OllamaDialect.render`.

    Mirrors the constructor signature of
    :class:`~flama.models.wire.dialect.llm.ollama.OllamaRenderer` exactly.
    """

    api: compat.Required[t.Literal["chat", "generate"]]
    model: compat.Required[str]


class OllamaDialect(Dialect[types.JSONSchema, OllamaRenderKwargs, OllamaAssembleKwargs]):
    """Ollama-compatible wire dialect.

    Binds three strategies that drive the :class:`~flama.models.wire.dialect.base.Dialect` façade:

    - :attr:`PARSER` -> :class:`~flama.models.wire.dialect.llm.ollama.OllamaParser` (L1 -> L2 input;
      handles Ollama's ``images: [...]`` sibling field by pre-splicing into canonical structured parts).
    - :attr:`RENDERER` -> :class:`~flama.models.wire.dialect.llm.ollama.OllamaRenderer` (L2 -> L1 streaming
      NDJSON).
    - :attr:`ASSEMBLER` -> :class:`~flama.models.wire.dialect.llm.ollama.OllamaAssembler` (L2 -> L1 buffered
      ``/api/chat`` or ``/api/generate`` envelope).
    """

    PARSER = OllamaParser
    RENDERER = OllamaRenderer
    ASSEMBLER = OllamaAssembler
