import dataclasses

__all__ = ["EngineDelta"]


@dataclasses.dataclass(frozen=True)
class EngineDelta:
    """A single output delta produced by an :class:`~flama.models.engine.backend.llm.base.LLMBackend`.

    :param text: Newly produced text fragment for this step.
    :param token_count: Number of tokens emitted in this delta, when known.
    :param finish_reason: Backend-native, unnormalised termination signal forwarded verbatim from the engine.
    """

    text: str = ""
    token_count: int | None = None
    finish_reason: str | None = None
