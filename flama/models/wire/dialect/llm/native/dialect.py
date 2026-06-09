import typing as t
import uuid

from flama import compat
from flama.http.responses.sse import ServerSentEvent
from flama.models.wire.dialect.base import Dialect, EventSource
from flama.models.wire.dialect.llm.native.assembler import NativeAssembleKwargs, NativeAssembler
from flama.models.wire.dialect.llm.native.parser import NativeParser
from flama.models.wire.dialect.llm.native.renderer import EventsRenderer

__all__ = ["NativeDialect", "NativeRenderKwargs"]


class NativeRenderKwargs(t.TypedDict, total=False):
    """Per-stream kwargs accepted by :meth:`NativeDialect.render`.

    Carries the SSE identity (``message_id``) and the optional resume / retry hints. Mirrors the constructor
    signature of :class:`~flama.models.wire.dialect.llm.native.EventsRenderer` exactly so
    :meth:`Dialect.render` can forward ``**kwargs`` directly.
    """

    message_id: compat.Required[uuid.UUID]
    resume_id: str | None
    retry: int | None


class NativeDialect(Dialect[ServerSentEvent]):
    """Native Flama wire dialect.

    L1 -> L2 input parsing is delegated to :class:`~flama.models.wire.dialect.llm.native.NativeParser` via
    :attr:`PARSER`. L2 -> L1 streaming output is delegated to
    :class:`~flama.models.wire.dialect.llm.native.EventsRenderer` via :attr:`RENDERER`. The dialect is
    stream-only; :attr:`ASSEMBLER` raises :class:`NotImplementedError` from
    :meth:`~flama.models.wire.dialect.base.Assembler.envelope` because there is no native buffered envelope
    shape (the buffered ``POST /query/`` handler renders its own channel-tagged response inline against the
    same :class:`~flama.models.wire.dialect.base.CoalescingRenderer` engine).
    """

    PARSER = NativeParser
    RENDERER = EventsRenderer
    ASSEMBLER = NativeAssembler

    @classmethod
    def render(
        cls, source: EventSource, /, **kwargs: compat.Unpack[NativeRenderKwargs]
    ) -> t.AsyncIterator[ServerSentEvent]:
        """Typed façade over :meth:`Dialect._render` naming the native render kwargs (``message_id``, ...)."""
        return cls._render(source, kwargs)

    @classmethod
    async def assemble(cls, source: EventSource, /, **kwargs: compat.Unpack[NativeAssembleKwargs]) -> dict[str, t.Any]:
        """Typed façade over :meth:`Dialect._assemble`. The native wire is stream-only, so this raises
        :class:`NotImplementedError` from :meth:`NativeAssembler.envelope`."""
        return await cls._assemble(source, kwargs)
