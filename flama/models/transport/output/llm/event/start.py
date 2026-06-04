import dataclasses
import typing as t

from flama.models.transport.output.llm.event.base import Event

__all__ = ["StartEvent"]


@dataclasses.dataclass(frozen=True)
class StartEvent(Event):
    """Lifecycle marker emitted before any content events.

    Persisted as the first line of a stream's cold-storage log so the JSONL file is fully self-describing.
    The SSE renderer translates this event into a ``message.start`` wire frame.

    :param id: Stable identifier for the generation (typically the buffer uuid hex).
    :param created: Unix timestamp at which the buffer was created.
    :param input_tokens: Prompt token count, when available.
    """

    KIND: t.ClassVar[t.Literal["start"]] = "start"

    id: str
    created: int
    input_tokens: int | None = None

    def payload(self) -> dict[str, t.Any]:
        """``{"id": ..., "created": ..., "input_tokens"?: ...}``."""
        body: dict[str, t.Any] = {"id": self.id, "created": self.created}
        if self.input_tokens is not None:
            body["input_tokens"] = self.input_tokens
        return body

    @classmethod
    def from_payload(cls, payload: dict[str, t.Any], /) -> "StartEvent":
        return cls(id=payload["id"], created=payload["created"], input_tokens=payload.get("input_tokens"))
