import dataclasses
import typing as t

from flama import types
from flama.models.transport.output.llm.event.base import Event

__all__ = ["StopEvent"]


@dataclasses.dataclass(frozen=True)
class StopEvent(Event):
    """Lifecycle marker emitted after all content events.

    Persisted as the last line of a stream's cold-storage log alongside the final stop reason and usage snapshot.
    The SSE renderer translates this event into a ``message.stop`` wire frame.

    :param stop_reason: Canonical stop reason; one of :data:`~flama.types.LLMStopReason`.
    :param output_tokens: Final output token usage total.
    """

    KIND: t.ClassVar[t.Literal["stop"]] = "stop"

    stop_reason: types.LLMTransportStopReason | None = None
    output_tokens: int | None = None

    def payload(self) -> dict[str, t.Any]:
        """Subset of populated fields; missing fields are omitted from the payload."""
        body: dict[str, t.Any] = {}
        if self.stop_reason is not None:
            body["stop_reason"] = self.stop_reason
        if self.output_tokens is not None:
            body["output_tokens"] = self.output_tokens
        return body

    @classmethod
    def from_payload(cls, payload: dict[str, t.Any], /) -> "StopEvent":
        return cls(stop_reason=payload.get("stop_reason"), output_tokens=payload.get("output_tokens"))
