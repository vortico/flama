import ast
import dataclasses
import typing as t

from flama._upgrade.operations._base import MARKER, ApplyResult, Operation, Todo
from flama._upgrade.operations.targets import Call, Member, Module, Symbol, Target
from flama._upgrade.source import Edit, Source

__all__ = ["Flag"]


@dataclasses.dataclass(frozen=True)
class Flag(Operation):
    """Record a manual follow-up wherever a target is used, without rewriting it.

    Imports of a module or symbol also get a ``# flama-upgrade: <note>`` marker appended. Calls and member accesses
    are only reported. Each follow-up reads as the target followed by ``note``, e.g. ``"`flama.cli` is now private"``.

    :param target: What to flag.
    :param note: Explanation surfaced in the marker and the report.
    """

    target: Target
    note: str

    @property
    def id(self) -> str:
        return f"flag:{self.target.kind}:{self.target.dotted}"

    def apply(self, source: Source) -> ApplyResult:
        match self.target:
            case Module() | Symbol():
                return self._flag_imports(source, self.target)
            case Call():
                return ApplyResult(source, False, tuple(self._flag_calls(source, self.target)))
            case Member():
                return ApplyResult(source, False, tuple(self._flag_members(source, self.target)))

    def _flag_imports(self, source: Source, target: Module | Symbol) -> ApplyResult:
        edits: list[Edit] = []
        todos: list[Todo] = []
        for node in source.imports:
            if not self._imports(node, target):
                continue
            end_line = t.cast(int, node.end_lineno)
            end_col = t.cast(int, node.end_col_offset)
            edits.append(Edit(end_line, end_col, end_line, end_col, f"  # {MARKER}: {self.note}"))
            todos.append(Todo(node.lineno, f"`{target.dotted}` {self.note}"))

        return ApplyResult(source.with_edits(edits), bool(edits), tuple(todos))

    @staticmethod
    def _imports(node: ast.Import | ast.ImportFrom, target: Module | Symbol) -> bool:
        if isinstance(target, Symbol):
            return (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == target.module
                and any(alias.name == target.name for alias in node.names)
            )
        if isinstance(node, ast.ImportFrom):
            return node.level == 0 and node.module == target.path
        return any(alias.name == target.path or alias.name.startswith(f"{target.path}.") for alias in node.names)

    def _flag_calls(self, source: Source, target: Call) -> list[Todo]:
        callees = {id(node) for node in source.symbol_references(target.symbol.module, target.symbol.name)}
        return [
            Todo(node.lineno, f"`{ast.get_source_segment(source.text, node.func)}(...)` {self.note}")
            for node in ast.walk(source.tree)
            if isinstance(node, ast.Call)
            and id(node.func) in callees
            and (not target.with_arguments or node.args or node.keywords)
        ]

    def _flag_members(self, source: Source, target: Member) -> list[Todo]:
        owners = {id(node) for node in source.symbol_references(target.symbol.module, target.symbol.name)}
        return [
            Todo(node.lineno, f"`{ast.get_source_segment(source.text, node)}` {self.note}")
            for node in ast.walk(source.tree)
            if isinstance(node, ast.Attribute) and node.attr == target.name and id(node.value) in owners
        ]
