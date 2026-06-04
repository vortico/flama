import abc
import dataclasses
import re
import typing as t

__all__ = ["MarkerScanner", "PassthroughScanner", "Scanner"]


_EventKind: t.TypeAlias = t.Literal["content", "open", "close"]


@dataclasses.dataclass(frozen=True)
class _Event:
    """Single tagged event yielded by :meth:`Scanner.scan`.

    The streaming FSM advances ``buffer = buffer[length:]`` on every event regardless of kind.
    ``open`` and ``close`` are role-agnostic events emitted by :class:`Scanner`; the FSM tags
    them as channel- or tool-shaped depending on which slot the scanner came from.

    :param kind: The discriminator.
    :param length: Number of characters consumed from the head of the scanned buffer.
    :param channel: Captured channel/inner name (only on ``open`` events with a captured group).
    """

    kind: _EventKind
    length: int
    channel: str | None = None


class Scanner(abc.ABC):
    """Common interface for any marker-pair detector usable in the channel or tool slot.

    Concrete subclasses are :class:`MarkerScanner` (literal/regex driven) and
    :class:`PassthroughScanner` (always-passthrough sentinel). The FSM consumes the ``Scanner``
    interface uniformly via :meth:`scan`; one-time fingerprinting at warmup goes through
    :meth:`detect`.
    """

    name: str

    @abc.abstractmethod
    def detect(self, s: str, /) -> bool:
        """Whether *s* exhibits this scanner's full marker cycle (or its open literal at minimum)."""
        ...

    @abc.abstractmethod
    def scan(self, s: str, /, *, inside: bool) -> _Event | None:
        """Scan *s* and return the next role-agnostic event, or :data:`None` to hold."""
        ...


@dataclasses.dataclass(frozen=True)
class MarkerScanner(Scanner):
    """Single concrete marker-pair scanner, usable in both the channel and tool slots.

    The :class:`_FSM` in :mod:`~flama.models.engine.llm.codec` decides whether an
    ``open`` / ``close`` event is a channel transition or a tool transition based on which
    slot the scanner came from, so one class covers both roles.

    The ``inner`` / ``separator`` fields support three-part open markers like Harmony's
    ``<|channel|>NAME<|message|>`` where the open marker spans two literals with a captured
    name in between, or Gemma 4's ``<|channel>NAME\\n`` where the captured name is followed
    by a separator literal. ``end=None`` denotes formats that close at EOS or are
    parser-driven (e.g. Mistral ``[TOOL_CALLS]``).

    :param name: Stable identifier surfaced in registry lookups, repr output, and logs.
    :param start: Literal opening tag (e.g. ``"<think>"``, ``"<|channel|>"``). Required.
    :param end: Literal closing tag, or :data:`None` for re-marker / EOS-bounded formats.
    :param inner: Optional regex source matched immediately after ``start``. When the match
        yields a value it is exposed via the open event's :attr:`_Event.channel` payload.
    :param separator: Optional literal that follows the captured ``inner`` match. Requires
        ``inner``.
    :param start_of_buffer_only: When :data:`True`, the open marker only fires when it
        coincides with the start of the buffer (after stripping any leading whitespace).
        Used by ``pythonic`` to avoid false positives on mid-text ``[`` characters.
    :raises ValueError: If ``name`` or ``start`` is empty, or if ``separator`` is set without
        ``inner``.
    """

    name: str
    start: str
    end: str | None = None
    inner: str | None = None
    separator: str | None = None
    start_of_buffer_only: bool = False

    open: re.Pattern[str] = dataclasses.field(init=False, repr=False, compare=False)
    close: re.Pattern[str] | None = dataclasses.field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("'name' must be a non-empty string")
        if not self.start:
            raise ValueError("'start' must be a non-empty string")
        if self.separator is not None and self.inner is None:
            raise ValueError("'separator' requires 'inner'")
        object.__setattr__(
            self,
            "open",
            re.compile(
                "".join(
                    [
                        re.escape(self.start),
                        f"(?P<inner>{self.inner})" if self.inner else "",
                        re.escape(self.separator) if self.separator else "",
                    ]
                )
            ),
        )
        object.__setattr__(self, "close", re.compile(re.escape(self.end)) if self.end else None)

    def detect(self, s: str, /) -> bool:
        """Whether *s* exhibits this scanner's full marker cycle (or its open literal at minimum).

        For two-sided patterns (``end != None``), evidence of *both* literals is required.
        For one-sided patterns (``end is None``), the open literal alone is enough; if
        :attr:`start_of_buffer_only` is set, the open literal must also coincide with the
        start of the (whitespace-stripped) buffer.
        """
        if self.start_of_buffer_only:
            if not s.lstrip().startswith(self.start):
                return False
        elif self.start not in s:
            return False
        return self.end is None or self.end in s

    def find_open(self, s: str, /) -> re.Match[str] | None:
        """Return a full open-marker match in *s*, or :data:`None`."""
        return self.open.search(s)

    def find_close(self, s: str, /) -> re.Match[str] | None:
        """Return a full close-marker match in *s*, or :data:`None`.

        Always :data:`None` when ``end`` is :data:`None` (parser-driven / re-marker formats).
        """
        return self.close.search(s) if self.close is not None else None

    def partial_prefix_index(self, s: str, /, *, end: bool) -> int:
        """Index in *s* where a held-back partial marker prefix begins.

        When the literal occurs in full, that occurrence is the only meaningful position;
        otherwise the tail of *s* is checked for a suffix-prefix overlap with the literal.
        Returns ``len(s)`` when nothing is held back. ``end=True`` looks at the close
        literal, ``end=False`` at the open literal.
        """
        literal = self.end if end else self.start
        if literal is None:
            return len(s)
        if (pos := s.find(literal)) != -1:
            return pos
        for k in range(min(len(literal) - 1, len(s)), 0, -1):
            if s.endswith(literal[:k]):
                return len(s) - k
        return len(s)

    def scan(self, s: str, /, *, inside: bool) -> _Event | None:
        """Scan *s* and return the next role-agnostic event, or :data:`None` to hold.

        Yields ``content`` for safe-to-emit prefix slices and ``open`` / ``close`` for marker
        boundaries. The caller (FSM) translates these into role-tagged transitions. ``inside=True``
        means the FSM has already consumed the open marker and is now scanning for the close marker
        (or, for re-marker formats with ``end=None``, the next open marker).

        :param s: Accumulated text deltas. Always non-empty (FSM gates on
            ``while self._buffer:``).
        :param inside: Whether the FSM has entered this pattern's region.
        :return: The next event, or :data:`None` if the buffer is a partial marker prefix
            and must be held until more input arrives.
        """
        if inside:
            return self._scan_inside(s)
        return self._scan_outside(s)

    def _scan_inside(self, s: str) -> _Event | None:
        if self.end is not None:
            m = self.find_close(s)
            if m is not None:
                if m.start() == 0:
                    return _Event(kind="close", length=m.end())
                return _Event(kind="content", length=m.start())
            boundary = self.partial_prefix_index(s, end=True)
            return _Event(kind="content", length=boundary) if boundary > 0 else None
        # Re-marker (end=None): body extends until next start, or until EOS if none seen yet.
        reopen = self.find_open(s)
        if reopen is not None:
            if reopen.start() == 0:
                return _Event(kind="close", length=0)
            return _Event(kind="content", length=reopen.start())
        boundary = self.partial_prefix_index(s, end=False)
        return _Event(kind="content", length=boundary) if boundary > 0 else None

    def _scan_outside(self, s: str) -> _Event | None:
        m_open = self.find_open(s)
        # `start_of_buffer_only` markers (e.g. pythonic `[`/`]`) use non-distinctive literals that legitimately
        # occur in regular text, so we can't safely treat a bare close as a stray; fall back to the open-only
        # legacy path for them.
        m_close = self.find_close(s) if not self.start_of_buffer_only else None
        # An open match is only "complete" when the captured `inner` can no longer extend with future input;
        # this mirrors the original holdback guard so stray-close detection never overrides a partial open.
        if m_open is not None and (self.inner is None or m_open.end() < len(s) or self.separator is not None):
            # Leftmost-wins: a complete open at or before a close beats the close (their roles differ via event
            # kind); a close that strictly precedes the open is handled below.
            if m_close is None or m_open.start() <= m_close.start():
                if self.start_of_buffer_only and s[: m_open.start()].strip():
                    return _Event(kind="content", length=m_open.start())
                if m_open.start() > 0:
                    return _Event(kind="content", length=m_open.start())
                return _Event(kind="open", length=m_open.end(), channel=m_open.groupdict().get("inner"))
        # Stray close while outside any region: emit a close event so the FSM can consume it silently rather than
        # letting the literal bytes leak through to the user (e.g. Gemma 4's empty prompt-prefix `<channel|>` that
        # the FSM never saw open).
        if m_close is not None:
            if m_close.start() > 0:
                return _Event(kind="content", length=m_close.start())
            return _Event(kind="close", length=m_close.end())
        # Conservative holdback: any partial prefix of either literal at the buffer tail blocks emission so a
        # marker split across deltas never leaks the head of its bytes as content. For
        # `start_of_buffer_only` markers we keep the legacy open-only holdback to avoid false positives on
        # ambiguous close literals.
        end_boundary = self.partial_prefix_index(s, end=True) if not self.start_of_buffer_only else len(s)
        boundary = min(self.partial_prefix_index(s, end=False), end_boundary)
        return _Event(kind="content", length=boundary) if boundary > 0 else None


class PassthroughScanner(Scanner):
    """Marker-less sentinel usable in both the channel and tool scanner slots.

    Always emits the buffer verbatim as a ``content`` event regardless of the FSM state, so
    both sides of the decoder converge on the same passthrough type. :meth:`detect` always
    returns :data:`False`, which excludes this sentinel from auto-detection iteration.
    """

    name: t.Final[t.Literal["passthrough"]] = "passthrough"

    def detect(self, s: str, /) -> bool:
        """Always :data:`False`; passthrough is the explicit fallback, never auto-detected."""
        return False

    def scan(self, s: str, /, *, inside: bool = False) -> _Event:  # pragma: no branch
        return _Event(kind="content", length=len(s))
