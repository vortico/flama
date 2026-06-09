import abc
import ast
import dataclasses
import typing as t

from flama.upgrade.source import Edit, Source

__all__ = ["Todo", "ApplyResult", "Operation", "MoveModule", "MoveSymbol", "RemoveSymbol"]

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


def _node_edit(node: ast.stmt | ast.expr, text: str) -> Edit:
    """Build an :class:`Edit` covering the full span of ``node``."""
    return Edit(
        node.lineno,
        node.col_offset,
        t.cast(int, node.end_lineno),
        t.cast(int, node.end_col_offset),
        text,
    )


def _render_from(module: str, aliases: t.Sequence[tuple[str, str | None]]) -> str:
    """Render a ``from <module> import ...`` statement from ``(name, asname)`` pairs."""
    names = ", ".join(name if asname is None else f"{name} as {asname}" for name, asname in aliases)
    return f"from {module} import {names}"


def _render_import(aliases: t.Sequence[tuple[str, str | None]]) -> str:
    """Render an ``import ...`` statement from ``(name, asname)`` pairs."""
    names = ", ".join(name if asname is None else f"{name} as {asname}" for name, asname in aliases)
    return f"import {names}"


class Operation(abc.ABC):
    """A single, reusable code transformation applied to one :class:`Source` at a time.

    Operations are version-agnostic building blocks; concrete upgrades compose them as data in
    :mod:`flama.upgrade.codemods`. Each operation is identified by a stable :attr:`id` so it can be
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


@dataclasses.dataclass(frozen=True)
class MoveModule(Operation):
    """Relocate every import of a module from ``old`` to ``new``.

    Rewrites ``from old import ...`` (including ``import *``) and aliased ``import old as x`` statements.
    A bare ``import old`` is left untouched with a follow-up, because its ``old.attr`` usages cannot be
    rewritten from the import alone.

    :param old: Fully-qualified module path in the source version.
    :param new: Fully-qualified module path in the target version.
    """

    old: str
    new: str

    @property
    def id(self) -> str:
        return f"move-module:{self.old}"

    def apply(self, source: Source) -> ApplyResult:
        edits: list[Edit] = []
        todos: list[Todo] = []
        for node in source.imports:
            if isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module == self.old:
                    edits.append(_node_edit(node, _render_from(self.new, [(a.name, a.asname) for a in node.names])))
            else:
                self._rewrite_import(node, edits, todos)

        return ApplyResult(source.with_edits(edits), bool(edits), tuple(todos))

    def _rewrite_import(self, node: ast.Import, edits: list[Edit], todos: list[Todo]) -> None:
        aliases: list[tuple[str, str | None]] = []
        changed = False
        for alias in node.names:
            if alias.name == self.old or alias.name.startswith(f"{self.old}."):
                target = f"{self.new}{alias.name[len(self.old) :]}"
                if alias.asname is None:
                    todos.append(
                        Todo(node.lineno, f"`import {alias.name}` is now `import {target}`; update dotted usages")
                    )
                    aliases.append((alias.name, alias.asname))
                else:
                    changed = True
                    aliases.append((target, alias.asname))
            else:
                aliases.append((alias.name, alias.asname))
        if changed:
            edits.append(_node_edit(node, _render_import(aliases)))


@dataclasses.dataclass(frozen=True)
class MoveSymbol(Operation):
    """Relocate and/or rename a single symbol imported from a module.

    Matches ``from <module> import <name>`` and rewrites the import to ``<to_module> import <to_name>``,
    splitting the statement when other names remain. When the symbol is renamed and imported without an
    alias, its in-scope references are rewritten too; if the name is shadowed or reassigned, a follow-up
    is emitted instead.

    :param module: Source module the symbol is imported from.
    :param name: Symbol name in the source version.
    :param to_module: Target module (defaults to ``module``).
    :param to_name: Target name (defaults to ``name``).
    """

    module: str
    name: str
    to_module: str | None = None
    to_name: str | None = None

    @property
    def target_module(self) -> str:
        return self.to_module or self.module

    @property
    def target_name(self) -> str:
        return self.to_name or self.name

    @property
    def id(self) -> str:
        return f"move-symbol:{self.module}:{self.name}"

    def apply(self, source: Source) -> ApplyResult:
        if self.target_module == self.module and self.target_name == self.name:
            return ApplyResult(source, False)

        edits: list[Edit] = []
        rename_anchor: int | None = None
        for node in source.imports:
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != self.module:
                continue
            match = next((alias for alias in node.names if alias.name == self.name), None)
            if match is None:
                continue
            edits.append(_node_edit(node, self._rewrite_import(node, match)))
            if match.asname is None and self.target_name != self.name:
                rename_anchor = node.lineno

        if rename_anchor is None:
            return ApplyResult(source.with_edits(edits), bool(edits))

        if source.is_rebound(self.name):
            todo = Todo(rename_anchor, f"`{self.name}` is now `{self.target_name}` but is shadowed; update usages")
            return ApplyResult(source.with_edits(edits), bool(edits), (todo,))

        edits.extend(_node_edit(reference, self.target_name) for reference in source.references(self.name))
        return ApplyResult(source.with_edits(edits), bool(edits))

    def _rewrite_import(self, node: ast.ImportFrom, match: ast.alias) -> str:
        remaining = [(alias.name, alias.asname) for alias in node.names if alias is not match]
        moved = _render_from(self.target_module, [(self.target_name, match.asname)])
        if not remaining:
            return moved
        return f"{_render_from(self.module, remaining)}\n{' ' * node.col_offset}{moved}"


@dataclasses.dataclass(frozen=True)
class RemoveSymbol(Operation):
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

    def apply(self, source: Source) -> ApplyResult:
        edits: list[Edit] = []
        todos: list[Todo] = []
        for node in source.imports:
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != self.module:
                continue
            if not any(alias.name == self.name for alias in node.names):
                continue
            end_line = t.cast(int, node.end_lineno)
            end_col = t.cast(int, node.end_col_offset)
            edits.append(Edit(end_line, end_col, end_line, end_col, f"  # {MARKER}: {self.note}"))
            todos.append(Todo(node.lineno, f"`{self.module}.{self.name}` was removed: {self.note}"))

        return ApplyResult(source.with_edits(edits), bool(edits), tuple(todos))
