import dataclasses
import typing as t

from flama.models.transport.output.llm.event._base import Event

__all__ = ["TextEvent"]


@dataclasses.dataclass(frozen=True)
class TextEvent(Event):
    """Channel-tagged text fragment.

    The ``channel`` field is an open string or :data:`None`. By default, content outside any marker pair lands on
    ``"output"`` (configurable via :attr:`ChannelPolicy.output`); marker matches surface a per-format channel name
    extracted from the open marker (e.g. ``"analysis"``, ``"thought"``). When a marker captures no identity at all
    (e.g. ``<think>...</think>``) the channel is :data:`None`, leaving naming to downstream consumers rather than
    coercing into a project-specific synonym. Custom decoders are free to introduce their own channel names.

    :param channel: Discriminator describing what kind of content ``text`` carries, or :data:`None` for an
        un-named capture.
    :param text: Raw text content for this block.
    """

    KIND: t.ClassVar[t.Literal["text"]] = "text"

    channel: str | None
    text: str

    def payload(self) -> dict[str, t.Any]:
        """``{"type": "text", "channel": ..., "text": ...}``."""
        return {"type": "text", "channel": self.channel, "text": self.text}

    def delta_payload(self) -> dict[str, t.Any]:
        """``{"type": "text.delta", "text": ...}``."""
        return {"type": "text.delta", "text": self.text}

    @classmethod
    def from_payload(cls, payload: dict[str, t.Any], /) -> "TextEvent":
        return cls(channel=payload.get("channel"), text=payload["text"])
