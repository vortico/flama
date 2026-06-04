import dataclasses
import typing as t

from flama.models.transport.output.llm.event.base import Event

__all__ = ["ToolEvent"]


@dataclasses.dataclass(frozen=True)
class ToolEvent(Event):
    """Event carrying a parsed tool-call request.

    Mirrors the OpenAI Chat Completions ``tool_calls[]`` element so consumers can dispatch directly. Tool events
    are emitted complete-by-construction: the parser yields one :class:`~flama.models.ToolCall` per call inside
    the marker-pair body, and the FSM mints a fresh id and produces one :class:`ToolEvent` per call. There is no
    incremental streaming inside a tool body.

    :param id: Synthesized identifier (``"call_<uuid4hex>"``) minted by the FSM.
    :param name: Function name.
    :param arguments: Parsed argument object.
    """

    KIND: t.ClassVar[t.Literal["tool"]] = "tool"

    id: str
    name: str
    arguments: dict[str, t.Any]

    def payload(self) -> dict[str, t.Any]:
        """``{"type": "tool", "id": ..., "name": ..., "arguments": ...}``."""
        return {"type": "tool", "id": self.id, "name": self.name, "arguments": self.arguments}

    def delta_payload(self) -> dict[str, t.Any]:
        """``{"type": "tool.delta", "name": ..., "arguments": ...}``."""
        return {"type": "tool.delta", "name": self.name, "arguments": self.arguments}

    @classmethod
    def from_payload(cls, payload: dict[str, t.Any], /) -> "ToolEvent":
        return cls(id=payload["id"], name=payload["name"], arguments=payload["arguments"])
