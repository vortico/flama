import ast
import typing as t

from flama._upgrade.operations._base import ApplyResult, Operation, Todo
from flama._upgrade.operations.targets import Call, Member
from flama._upgrade.operations.transforms import CallParts, CallTransform, MemberTransform
from flama._upgrade.source import Edit, Source

__all__ = ["Rewrite"]


def _drop_nested(nodes: t.Sequence[ast.Call]) -> list[ast.Call]:
    """Drop calls whose span is contained within another call, to avoid overlapping edits."""

    def span(node: ast.Call) -> tuple[int, int, int, int]:
        return (node.lineno, node.col_offset, t.cast(int, node.end_lineno), t.cast(int, node.end_col_offset))

    result: list[ast.Call] = []
    for node in nodes:
        a = span(node)
        if not any(other is not node and span(other)[:2] <= a[:2] and a[2:] <= span(other)[2:] for other in nodes):
            result.append(node)
    return result


class Rewrite(Operation):
    """Rewrite the calls to a symbol, or the accesses to one of its members, through a chain of transforms.

    For calls, each matched call is split into its callee and arguments, passed through every
    :class:`~flama._upgrade.operations.transforms.CallTransform` in order, and rendered back once. For members,
    each access is offered to every :class:`~flama._upgrade.operations.transforms.MemberTransform` in order, and the
    first replacement wins. Transforms may also emit follow-ups.

    :param target: Calls or member accesses to rewrite.
    :param transforms: Transforms to apply, of the kind the target takes.
    """

    target: Call | Member
    transforms: tuple[CallTransform, ...] | tuple[MemberTransform, ...]

    @t.overload
    def __init__(self, target: Call, /, *transforms: CallTransform) -> None: ...
    @t.overload
    def __init__(self, target: Member, /, *transforms: MemberTransform) -> None: ...
    def __init__(self, target: Call | Member, /, *transforms: CallTransform | MemberTransform) -> None:
        expected = CallTransform if isinstance(target, Call) else MemberTransform
        if not transforms or not all(isinstance(transform, expected) for transform in transforms):
            raise TypeError(f"A {target.kind} rewrite needs one or more {expected.__name__}")
        self.target = target
        self.transforms = t.cast(tuple[CallTransform, ...] | tuple[MemberTransform, ...], transforms)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target!r}, {', '.join(map(repr, self.transforms))})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Rewrite) and (self.target, self.transforms) == (other.target, other.transforms)

    def __hash__(self) -> int:
        return hash((self.target, self.transforms))

    @property
    def id(self) -> str:
        return f"rewrite:{self.target.kind}:{self.target.dotted}"

    def apply(self, source: Source) -> ApplyResult:
        if isinstance(self.target, Call):
            return self._rewrite_calls(source, self.target, t.cast(tuple[CallTransform, ...], self.transforms))

        return self._rewrite_members(source, self.target, t.cast(tuple[MemberTransform, ...], self.transforms))

    def _rewrite_calls(self, source: Source, target: Call, transforms: tuple[CallTransform, ...]) -> ApplyResult:
        callees = {id(node) for node in source.symbol_references(target.symbol.module, target.symbol.name)}
        calls = _drop_nested(
            [
                node
                for node in ast.walk(source.tree)
                if isinstance(node, ast.Call)
                and id(node.func) in callees
                and (not target.with_arguments or node.args or node.keywords)
            ]
        )

        edits: list[Edit] = []
        todos: list[Todo] = []
        for node in calls:
            original = CallParts.from_node(source.text, node)
            parts = original
            for transform in transforms:
                parts, todo = transform(parts, node.lineno)
                if todo is not None:
                    todos.append(todo)
            if parts != original:
                edits.append(Edit.from_node(node, parts.render()))

        if not edits:
            return ApplyResult(source, False, tuple(todos))

        rewritten = source.with_edits(edits)
        for transform in transforms:
            rewritten = transform.finalize(rewritten, target.symbol)
        return ApplyResult(rewritten, True, tuple(todos))

    def _rewrite_members(self, source: Source, target: Member, transforms: tuple[MemberTransform, ...]) -> ApplyResult:
        owners = {id(node) for node in source.symbol_references(target.symbol.module, target.symbol.name)}
        members = {
            id(node): node
            for node in ast.walk(source.tree)
            if isinstance(node, ast.Attribute) and node.attr == target.name and id(node.value) in owners
        }
        if not members:
            return ApplyResult(source, False)

        accesses: list[tuple[ast.Attribute, ast.Attribute, str | None]] = []
        picked: set[int] = set()
        for node in ast.walk(source.tree):
            if isinstance(node, ast.Attribute) and id(node.value) in members:
                picked.add(id(node.value))
                accesses.append((node, members[id(node.value)], node.attr))
        accesses.extend((node, node, None) for key, node in members.items() if key not in picked)

        edits: list[Edit] = []
        todos: list[Todo] = []
        for span, member, value in accesses:
            written = t.cast(str, ast.get_source_segment(source.text, member))
            for transform in transforms:
                replacement, todo = transform(written, value, span.lineno)
                if todo is not None:
                    todos.append(todo)
                if replacement is not None:
                    edits.append(Edit.from_node(span, replacement))
                    break

        return ApplyResult(source.with_edits(edits), bool(edits), tuple(todos))
