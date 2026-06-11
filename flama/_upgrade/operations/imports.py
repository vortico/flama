import ast
import dataclasses

from flama._upgrade.operations._base import ApplyResult, Operation, Todo
from flama._upgrade.source import Edit, ImportStatement, Source

__all__ = ["MoveModule", "MoveSymbol"]


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
                    statement = ImportStatement(self.new, tuple((a.name, a.asname) for a in node.names))
                    edits.append(Edit.from_node(node, statement.render()))
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
            edits.append(Edit.from_node(node, ImportStatement(None, tuple(aliases)).render()))


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
            edits.append(Edit.from_node(node, self._rewrite_import(node, match)))
            if match.asname is None and self.target_name != self.name:
                rename_anchor = node.lineno

        if rename_anchor is None:
            return ApplyResult(source.with_edits(edits), bool(edits))

        if source.is_rebound(self.name):
            todo = Todo(rename_anchor, f"`{self.name}` is now `{self.target_name}` but is shadowed; update usages")
            return ApplyResult(source.with_edits(edits), bool(edits), (todo,))

        edits.extend(Edit.from_node(reference, self.target_name) for reference in source.references(self.name))
        return ApplyResult(source.with_edits(edits), bool(edits))

    def _rewrite_import(self, node: ast.ImportFrom, match: ast.alias) -> str:
        remaining = [(alias.name, alias.asname) for alias in node.names if alias is not match]
        moved = ImportStatement(self.target_module, ((self.target_name, match.asname),)).render()
        if not remaining:
            return moved
        return f"{ImportStatement(self.module, tuple(remaining)).render()}\n{' ' * node.col_offset}{moved}"
