import dataclasses
import typing as t

from flama.models.transport.output.llm.event.base import Event

__all__ = ["TraceEvent"]


@dataclasses.dataclass(frozen=True)
class TraceEvent(Event):
    """Out-of-band metadata event interleaved with content.

    The decoder forwards :class:`TraceEvent` events from the backend (via
    :class:`~flama.models.engine.backend.llm.EngineDelta`) so downstream consumers can drive throttled
    ``message.delta`` and final ``message.stop`` frames carrying token usage and the engine-level
    ``finish_reason``. Traces never reach the buffered ``query`` envelope's ``blocks`` array; they only inform
    the streaming wire format.

    :param token_count: Number of tokens emitted alongside the corresponding delta, when known.
    :param finish_reason: Backend-native termination signal preserved verbatim from
        :attr:`~flama.models.engine.backend.llm.EngineDelta.finish_reason`.
    """

    KIND: t.ClassVar[t.Literal["trace"]] = "trace"

    token_count: int | None = None
    finish_reason: str | None = None

    def payload(self) -> dict[str, t.Any]:
        """``{"token_count": ..., "finish_reason": ...}``."""
        return {"token_count": self.token_count, "finish_reason": self.finish_reason}

    @classmethod
    def from_payload(cls, payload: dict[str, t.Any], /) -> "TraceEvent":
        return cls(token_count=payload.get("token_count"), finish_reason=payload.get("finish_reason"))
