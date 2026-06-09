import typing as t

from flama import compat
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent
from flama.models.wire.dialect.base import Assembler

__all__ = ["NativeAssembleKwargs", "NativeAssembler"]


class NativeAssembleKwargs(t.TypedDict, total=False):
    """Empty kwargs payload; native :meth:`Assembler.envelope` accepts none.

    Bound on :class:`~flama.models.wire.dialect.llm.native.NativeDialect` so the type-checker still rejects
    accidental kwargs on :meth:`Dialect.assemble` calls against the native dialect.
    """


class NativeAssembler(Assembler):
    """L2 -> native buffered envelope strategy.

    The native dialect is stream-only; :meth:`envelope` raises :class:`NotImplementedError` unconditionally.
    The buffered ``POST /query/`` handler renders its own channel-tagged response inline against the same
    :class:`~flama.models.wire.dialect.base.CoalescingRenderer` engine.
    """

    @classmethod
    def envelope(
        cls,
        events: tuple[Event, ...],
        /,
        *,
        start: StartEvent,
        stop: StopEvent,
        **kwargs: compat.Unpack[NativeAssembleKwargs],
    ) -> dict[str, t.Any]:
        raise NotImplementedError("Native dialect is stream-only; no buffered envelope exists")
