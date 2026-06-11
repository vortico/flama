import abc
import ast
import dataclasses
import typing as t

from flama._upgrade.operations._base import MARKER, ApplyResult, Operation, Todo
from flama._upgrade.source import Edit, Source

__all__ = ["RemoveSymbol", "FlagModule"]


class _FlagOperation(Operation):
    """Base for operations that flag matching imports with a marker, without rewriting them.

    For every import statement a subclass :meth:`_matches`, a ``# flama-upgrade: <note>`` marker is
    appended and the subclass :meth:`_todo` is recorded as a manual follow-up. Used for symbols and
    modules that have no automatic replacement, pointing users at the public API instead.
    """

    note: str

    @abc.abstractmethod
    def _matches(self, node: ast.Import | ast.ImportFrom) -> bool:
        """Whether ``node`` imports the flagged symbol or module."""
        ...

    @abc.abstractmethod
    def _todo(self, node: ast.Import | ast.ImportFrom) -> Todo:
        """The manual follow-up to record for a matched ``node``."""
        ...

    def apply(self, source: Source) -> ApplyResult:
        edits: list[Edit] = []
        todos: list[Todo] = []
        for node in source.imports:
            if not self._matches(node):
                continue
            end_line = t.cast(int, node.end_lineno)
            end_col = t.cast(int, node.end_col_offset)
            edits.append(Edit(end_line, end_col, end_line, end_col, f"  # {MARKER}: {self.note}"))
            todos.append(self._todo(node))

        return ApplyResult(source.with_edits(edits), bool(edits), tuple(todos))


@dataclasses.dataclass(frozen=True)
class RemoveSymbol(_FlagOperation):
    """Flag a removed symbol that has no automatic replacement.

    Leaves ``from <module> import <name>`` in place, appends a ``# flama-upgrade: <note>`` marker to the
    statement, and records a manual follow-up.

    :param module: Module the removed symbol was imported from.
    :param name: Removed symbol name.
    :param note: Explanation surfaced in the marker and the report.
    """

    module: str
    name: str
    note: str

    @property
    def id(self) -> str:
        return f"remove-symbol:{self.module}:{self.name}"

    def _matches(self, node: ast.Import | ast.ImportFrom) -> bool:
        return (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == self.module
            and any(alias.name == self.name for alias in node.names)
        )

    def _todo(self, node: ast.Import | ast.ImportFrom) -> Todo:
        return Todo(node.lineno, f"`{self.module}.{self.name}` was removed: {self.note}")


@dataclasses.dataclass(frozen=True)
class FlagModule(_FlagOperation):
    """Flag imports of a module that was removed or made private, without rewriting them.

    Appends a ``# flama-upgrade: <note>`` marker to ``from <module> import ...`` and ``import <module>``
    statements (including dotted submodules and ``module`` prefixes) and records a manual follow-up. Used
    for modules that have no public replacement, so users are pointed at the public API instead of a
    private one.

    :param module: Fully-qualified module path that is gone or now private.
    :param note: Explanation surfaced in the marker and the report.
    """

    module: str
    note: str

    @property
    def id(self) -> str:
        return f"flag-module:{self.module}"

    def _matches(self, node: ast.Import | ast.ImportFrom) -> bool:
        if isinstance(node, ast.ImportFrom):
            return node.level == 0 and node.module == self.module
        return any(alias.name == self.module or alias.name.startswith(f"{self.module}.") for alias in node.names)

    def _todo(self, node: ast.Import | ast.ImportFrom) -> Todo:
        return Todo(node.lineno, f"`{self.module}` {self.note}")
