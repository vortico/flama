import ast
import dataclasses
import typing as t

from flama._upgrade.operations._base import ApplyResult, Operation, Todo
from flama._upgrade.operations.targets import Module, Symbol
from flama._upgrade.source import Edit, ImportStatement, Source

__all__ = ["Move"]


@dataclasses.dataclass(frozen=True, init=False)
class Move(Operation):
    """Relocate and/or rename a module or a symbol, rewriting its imports and references.

    For a module, ``from old import ...`` (including ``import *``) and aliased ``import old as x`` statements are
    rewritten; a bare ``import old`` is left with a follow-up, because its ``old.attr`` usages cannot be rewritten
    from the import alone.

    For a symbol, ``from module import name`` is rewritten, splitting the statement when other names remain. When
    the symbol is renamed and imported without an alias, its references are rewritten too, or flagged when the name
    is shadowed. References through the module (``exceptions.Name``) are renamed in place when the symbol stays in
    its module, and flagged when it moves to another one.

    :param old: Module or symbol in the source version.
    :param new: Module or symbol, of the same kind, in the target version.
    """

    old: Module | Symbol
    new: Module | Symbol

    @t.overload
    def __init__(self, old: Module, new: Module) -> None: ...
    @t.overload
    def __init__(self, old: Symbol, new: Symbol) -> None: ...
    def __init__(self, old: Module | Symbol, new: Module | Symbol) -> None:
        if type(old) is not type(new):
            raise TypeError(f"Cannot move a {old.kind} to a {new.kind}")
        object.__setattr__(self, "old", old)
        object.__setattr__(self, "new", new)

    @property
    def id(self) -> str:
        return f"move:{self.old.kind}:{self.old.dotted}"

    def apply(self, source: Source) -> ApplyResult:
        if self.old == self.new:
            return ApplyResult(source, False)
        if isinstance(self.old, Module) and isinstance(self.new, Module):
            return self._move_module(source, self.old.path, self.new.path)

        return self._move_symbol(source, t.cast(Symbol, self.old), t.cast(Symbol, self.new))

    def _move_module(self, source: Source, old: str, new: str) -> ApplyResult:
        edits: list[Edit] = []
        todos: list[Todo] = []
        for node in source.imports:
            if isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module == old:
                    statement = ImportStatement(new, tuple((a.name, a.asname) for a in node.names))
                    edits.append(Edit.from_node(node, statement.render()))
                continue

            aliases: list[tuple[str, str | None]] = []
            changed = False
            for alias in node.names:
                if alias.name == old or alias.name.startswith(f"{old}."):
                    target = f"{new}{alias.name[len(old) :]}"
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

        return ApplyResult(source.with_edits(edits), bool(edits), tuple(todos))

    def _move_symbol(self, source: Source, old: Symbol, new: Symbol) -> ApplyResult:
        edits: list[Edit] = []
        todos: list[Todo] = []
        rename_anchor: int | None = None
        for node in source.imports:
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != old.module:
                continue
            match = next((alias for alias in node.names if alias.name == old.name), None)
            if match is None:
                continue
            edits.append(Edit.from_node(node, self._rewrite_import(node, match, old, new)))
            if match.asname is None and new.name != old.name:
                rename_anchor = node.lineno

        if rename_anchor is not None:
            if source.is_rebound(old.name):
                todos.append(Todo(rename_anchor, f"`{old.name}` is now `{new.name}` but is shadowed; update usages"))
            else:
                edits.extend(Edit.from_node(reference, new.name) for reference in source.references(old.name))

        for reference in source.attribute_references(old.module, old.name):
            if new.module == old.module:
                end_line = t.cast(int, reference.end_lineno)
                end_col = t.cast(int, reference.end_col_offset)
                edits.append(Edit(end_line, end_col - len(old.name), end_line, end_col, new.name))
            else:
                todos.append(Todo(reference.lineno, f"`{old.dotted}` is now `{new.dotted}`; update this reference"))

        return ApplyResult(source.with_edits(edits), bool(edits), tuple(todos))

    @staticmethod
    def _rewrite_import(node: ast.ImportFrom, match: ast.alias, old: Symbol, new: Symbol) -> str:
        remaining = [(alias.name, alias.asname) for alias in node.names if alias is not match]
        moved = ImportStatement(new.module, ((new.name, match.asname),)).render()
        if new.module == old.module and (new.name, match.asname) in remaining:
            return ImportStatement(old.module, tuple(remaining)).render()
        if not remaining:
            return moved
        return f"{ImportStatement(old.module, tuple(remaining)).render()}\n{' ' * node.col_offset}{moved}"
