import dataclasses
import typing as t

__all__ = ["Tool"]


@dataclasses.dataclass(frozen=True)
class Tool:
    """Function-tool spec advertised to the model.

    Lives at the transport-canonical layer (L2): wire-format dicts (OpenAI / Ollama / Native dialects all use the
    same ``{"type": "function", "function": {...}}`` envelope) are translated into :class:`Tool` instances by each
    serving's :meth:`~flama.models.resources.serving.llm._base.LLMServing.parse` classmethod, and fed
    engine-side via :meth:`~flama.models.engine.backend.llm._base.LLMBackend.prepare_input` on the way out.
    The wire envelope is rebuilt
    only at the chat-template boundary so in-process code paths walk a single flat shape.

    Sibling of :class:`~flama.models.transport.input.llm.message.Message` at the request layer (request bodies advertise
    ``messages`` and ``tools`` side by side). Distinct from :class:`~flama.models.transport.input.llm.message.ToolCall`,
    which is a *child* of :class:`~flama.models.transport.input.llm.message.Message` modelling the assistant's
    *outgoing*
    tool invocations and keeps its ``function`` payload free-form to absorb dialect differences.

    :param name: Function name advertised to the model.
    :param description: Optional human-readable description.
    :param parameters: JSON Schema object describing the function arguments.
    :cvar type: Wire-format discriminator. Pinned to ``"function"``; widening this to a :class:`typing.Literal` union
        (or promoting :class:`Tool` to an abstract base) is the path forward when non-function tool kinds
        (``code_interpreter``, ``retrieval``, ...) need to land.
    """

    name: str
    description: str | None = None
    parameters: dict[str, t.Any] = dataclasses.field(default_factory=dict)
    type: t.ClassVar[t.Literal["function"]] = "function"

    def __post_init__(self) -> None:
        """Enforce L2 invariants regardless of how the :class:`Tool` was built.

        Applies equally to direct construction (tests, programmatic use) and to dialect parsers in each serving
        layer.

        :raises ValueError: When ``name`` is empty or non-string, ``description`` is set to a non-string, or
            ``parameters`` is not a mapping.
        """
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("'name' must be a non-empty string")
        if self.description is not None and not isinstance(self.description, str):
            raise ValueError("'description' must be a string when set")
        if not isinstance(self.parameters, dict):
            raise ValueError("'parameters' must be an object")
