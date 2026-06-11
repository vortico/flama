import abc
import dataclasses
import typing as t

from flama._upgrade.source import Source

__all__ = ["MARKER", "Todo", "ApplyResult", "Operation"]

MARKER: t.Final[str] = "flama-upgrade"


@dataclasses.dataclass(frozen=True)
class Todo:
    """A manual follow-up an operation could not perform automatically.

    :param line: 1-based line the follow-up relates to (0 when not tied to a specific line).
    :param message: Human-readable description of the action the user must take.
    """

    line: int
    message: str


@dataclasses.dataclass(frozen=True)
class ApplyResult:
    """The outcome of applying an :class:`Operation` to a :class:`Source`.

    :param source: The (possibly rewritten) source.
    :param changed: Whether any edit was applied.
    :param todos: Manual follow-ups the operation emitted.
    """

    source: Source
    changed: bool
    todos: tuple[Todo, ...] = ()


class Operation(abc.ABC):
    """A single, reusable code transformation applied to one :class:`Source` at a time.

    Operations are version-agnostic building blocks; concrete upgrades compose them as data in
    :mod:`flama._upgrade.codemods`. Each operation is identified by a stable :attr:`id` so it can be
    targeted via the CLI ``--select`` / ``--skip`` options.
    """

    @property
    @abc.abstractmethod
    def id(self) -> str:
        """Stable identifier used for selecting or skipping the operation."""
        ...

    @abc.abstractmethod
    def apply(self, source: Source) -> ApplyResult:
        """Apply the transformation to ``source`` and return the result."""
        ...
