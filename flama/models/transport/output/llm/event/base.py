import abc
import typing as t

from flama import types

__all__ = ["Event"]


class Event(abc.ABC):
    """Discriminated unit of LLM output and stream lifecycle.

    Models emit several kinds of output that downstream code needs to handle separately: free-form text (with
    channel tags for reasoning vs. answer), structured tool calls (function name + parsed argument object),
    out-of-band metadata (token counts, finish reasons), and stream lifecycle markers (message start / stop). All
    are surfaced as :class:`Event` subclasses with a :attr:`KIND` discriminator so callers dispatch on a single
    string and the durable on-disk representation is uniform.

    Subclasses implement :meth:`payload` (full descriptor used by the buffered query envelope, the SSE
    ``block.start`` frame, and the JSONL log line). :meth:`delta_payload` defaults to :meth:`payload` but is
    overridden where the SSE ``block.delta`` frame carries a different shape (text channel deltas, tool call
    deltas). :meth:`to_dict` and :meth:`from_dict` provide a tagged round-trip for cold-storage backends.
    """

    KIND: t.ClassVar[types.LLMTransportEvent]
    _REGISTRY: t.ClassVar[dict[types.LLMTransportEvent, type["Event"]] | None] = None

    @classmethod
    def _resolve(cls, kind: types.LLMTransportEvent) -> type["Event"]:
        """Lazily resolve the :class:`Event` subclass registered for *kind*.

        Concrete event types are imported on first call so the side-effect-free
        ``from flama.models.transport.output.llm.event.base import Event`` does not pull every
        event type into the import graph. Subsequent calls reuse the cached :attr:`_REGISTRY`.

        :param kind: Event discriminator persisted on the wire.
        :return: :class:`Event` subclass registered for *kind*.
        :raises KeyError: If *kind* is not a registered event type.
        """
        if cls._REGISTRY is None:
            from flama.models.transport.output.llm.event.start import StartEvent
            from flama.models.transport.output.llm.event.stop import StopEvent
            from flama.models.transport.output.llm.event.text import TextEvent
            from flama.models.transport.output.llm.event.tool import ToolEvent
            from flama.models.transport.output.llm.event.trace import TraceEvent

            cls._REGISTRY = {
                "start": StartEvent,
                "stop": StopEvent,
                "text": TextEvent,
                "tool": ToolEvent,
                "trace": TraceEvent,
            }
        return cls._REGISTRY[kind]

    @abc.abstractmethod
    def payload(self) -> dict[str, t.Any]:
        """Wire-shaped descriptor for this block (full content)."""
        ...

    def delta_payload(self) -> dict[str, t.Any]:
        """Wire-shaped delta payload for SSE ``block.delta`` events. Defaults to :meth:`payload`."""
        return self.payload()

    def to_dict(self) -> dict[str, t.Any]:
        """Dump a block into a proper dict.

        :return: The dict serialization of this block.
        """
        return {"kind": self.KIND, **self.payload()}

    @classmethod
    def from_dict(cls, obj: dict[str, t.Any], /) -> "Event":
        """Rehydrate a block from the dict produced by :meth:`to_dict`.

        :param obj: Mapping with a ``kind`` discriminator and the subclass-specific fields.
        :return: The rehydrated :class:`Event` instance.
        :raises KeyError: If the discriminator is missing or unknown.
        """
        payload = dict(obj)
        kind = payload.pop("kind")
        return cls._resolve(kind).from_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, t.Any], /) -> "Event":
        """Construct an instance from the payload returned by :meth:`payload` (no discriminator)."""
        return cls(**payload)
