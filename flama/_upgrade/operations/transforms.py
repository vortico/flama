import abc
import ast
import dataclasses
import typing as t

from flama._upgrade.operations._base import Todo
from flama._upgrade.source import Edit, ImportStatement, Keyword, Source

if t.TYPE_CHECKING:
    from flama._upgrade.operations.targets import Symbol

__all__ = [
    "Argument",
    "CallParts",
    "CallTransform",
    "PromoteKeyword",
    "DropKeyword",
    "RenameKeyword",
    "RenameMethod",
    "MapArgument",
    "Require",
    "Unwrap",
    "MemberTransform",
    "MapValue",
]


@dataclasses.dataclass(frozen=True)
class Argument:
    """A positional call argument.

    :param text: Source of the argument.
    :param node: Node it was parsed from, or ``None`` when a transform produced it.
    """

    text: str
    node: ast.expr | None = None


@dataclasses.dataclass(frozen=True)
class CallParts:
    """A call split into the parts call transforms work on.

    :param func: Source of the callee.
    :param args: Positional arguments.
    :param keywords: Keyword arguments, including ``**`` unpackings.
    """

    func: str
    args: tuple[Argument, ...]
    keywords: tuple[Keyword, ...]

    @classmethod
    def from_node(cls, text: str, node: ast.Call) -> "CallParts":
        """Split a parsed call, reading its parts from ``text``."""
        return cls(
            func=t.cast(str, ast.get_source_segment(text, node.func)),
            args=tuple(Argument(t.cast(str, ast.get_source_segment(text, arg)), arg) for arg in node.args),
            keywords=tuple(Keyword.from_node(text, keyword) for keyword in node.keywords),
        )

    def render(self) -> str:
        """Render the call back to source."""
        return f"{self.func}({', '.join([*(arg.text for arg in self.args), *(k.render() for k in self.keywords)])})"


def _frozen(values: t.Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(values.items())


class CallTransform(abc.ABC):
    """A change to the arguments or callee of a call, applied by :class:`~flama._upgrade.operations.Rewrite`."""

    @abc.abstractmethod
    def __call__(self, call: CallParts, line: int) -> tuple[CallParts, Todo | None]:
        """Transform ``call``, found at ``line``, returning the result and an optional follow-up."""
        ...

    def finalize(self, source: Source, symbol: "Symbol") -> Source:
        """Post-process the source once every matched call is rewritten (default: unchanged)."""
        return source


@dataclasses.dataclass(frozen=True)
class PromoteKeyword(CallTransform):
    """Pass a keyword argument as the first positional one (``Resp(content=x)`` -> ``Resp(x)``).

    :param keyword: Keyword argument to promote.
    """

    keyword: str

    def __call__(self, call: CallParts, line: int) -> tuple[CallParts, Todo | None]:
        match = next((keyword for keyword in call.keywords if keyword.arg == self.keyword), None)
        if match is None:
            return call, None

        return dataclasses.replace(
            call,
            args=(Argument(match.value), *call.args),
            keywords=tuple(keyword for keyword in call.keywords if keyword is not match),
        ), None


@dataclasses.dataclass(frozen=True)
class DropKeyword(CallTransform):
    """Drop a keyword argument the callee no longer accepts.

    :param keyword: Keyword argument to drop.
    :param note: Optional follow-up for each call it is dropped from.
    """

    keyword: str
    note: str = ""

    def __call__(self, call: CallParts, line: int) -> tuple[CallParts, Todo | None]:
        if not any(keyword.arg == self.keyword for keyword in call.keywords):
            return call, None

        keywords = tuple(keyword for keyword in call.keywords if keyword.arg != self.keyword)
        return dataclasses.replace(call, keywords=keywords), Todo(line, self.note) if self.note else None


@dataclasses.dataclass(frozen=True)
class RenameKeyword(CallTransform):
    """Pass a keyword argument under the name the callee now takes (``f(old=x)`` -> ``f(new=x)``).

    :param old: Keyword argument in the source version.
    :param new: Keyword argument in the target version.
    """

    old: str
    new: str

    def __call__(self, call: CallParts, line: int) -> tuple[CallParts, Todo | None]:
        if not any(keyword.arg == self.old for keyword in call.keywords):
            return call, None

        keywords = tuple(
            dataclasses.replace(keyword, arg=self.new) if keyword.arg == self.old else keyword
            for keyword in call.keywords
        )
        return dataclasses.replace(call, keywords=keywords), None


@dataclasses.dataclass(frozen=True)
class RenameMethod(CallTransform):
    """Call a method by the name it now has (``obj.old(...)`` -> ``obj.new(...)``).

    :param name: Method name in the target version.
    """

    name: str

    def __call__(self, call: CallParts, line: int) -> tuple[CallParts, Todo | None]:
        owner, dot, _ = call.func.rpartition(".")
        return dataclasses.replace(call, func=f"{owner}{dot}{self.name}"), None


@dataclasses.dataclass(frozen=True)
class MapArgument(CallTransform):
    """Replace a positional argument with the literal that now stands for it.

    The argument is looked up by its trailing name, so both ``hashlib.sha256`` and a bare ``sha256`` match the same
    entry. An argument that already is a string is left alone, so the rewrite can run more than once, and one the
    mapping does not cover emits a follow-up.

    :param index: Position of the argument.
    :param values: Argument name to the literal that replaces it.
    :param note: Follow-up message for arguments the mapping does not cover.
    """

    index: int
    values: t.Mapping[str, str]
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _frozen(self.values))

    def __call__(self, call: CallParts, line: int) -> tuple[CallParts, Todo | None]:
        if len(call.args) <= self.index:
            return call, None

        argument = call.args[self.index]
        match argument.node:
            case ast.Constant(value=str()):
                return call, None
            case ast.Attribute(attr=name) | ast.Name(id=name):
                literal = dict(self.values).get(name)
            case _:
                literal = None

        if literal is None:
            return call, Todo(line, self.note or f"`{call.func}({argument.text})` now takes a literal")

        args = (*call.args[: self.index], Argument(f'"{literal}"'), *call.args[self.index + 1 :])
        return dataclasses.replace(call, args=args), None


@dataclasses.dataclass(frozen=True, init=False)
class Require(CallTransform):
    """Flag calls passing none of the arguments the callee now requires.

    A call passing any positional argument, any of ``names`` or a ``**`` unpacking satisfies the requirement.

    :param names: Keyword arguments any of which satisfies the requirement.
    :param note: Follow-up message for calls that pass none of them.
    """

    names: tuple[str, ...]
    note: str = ""

    def __init__(self, *names: str, note: str = "") -> None:
        object.__setattr__(self, "names", names)
        object.__setattr__(self, "note", note)

    def __call__(self, call: CallParts, line: int) -> tuple[CallParts, Todo | None]:
        if call.args or any(keyword.arg in self.names or keyword.arg is None for keyword in call.keywords):
            return call, None

        return call, Todo(line, self.note or f"`{call.func}(...)` now requires `{self.names[0]}`")


@dataclasses.dataclass(frozen=True)
class Unwrap(CallTransform):
    """Make the first positional argument the callee (``Wrapper(inner, *rest)`` -> ``inner(*rest)``).

    Every unwrapped call emits a follow-up, because the unwrapped object may itself need changes.

    :param note: Follow-up message, prefixed with the unwrapped callee.
    :param prune_import: Remove the wrapper's import once nothing references it.
    """

    note: str
    prune_import: bool = True

    def __call__(self, call: CallParts, line: int) -> tuple[CallParts, Todo | None]:
        if not call.args:
            return call, None

        first, *rest = call.args
        if isinstance(first.node, ast.Starred):
            return call, Todo(line, f"`{call.func}(...)` wraps a starred argument; unwrap it manually")

        return dataclasses.replace(call, func=first.text, args=tuple(rest)), Todo(line, f"`{first.text}` {self.note}")

    def finalize(self, source: Source, symbol: "Symbol") -> Source:
        binding = source.local_binding(symbol.module, symbol.name)
        if not self.prune_import or binding is None:
            return source
        if any(isinstance(node, ast.Name) and node.id == binding for node in ast.walk(source.tree)):
            return source

        for node in source.imports:
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != symbol.module:
                continue
            remaining = [(alias.name, alias.asname) for alias in node.names if (alias.asname or alias.name) != binding]
            if len(remaining) == len(node.names):
                continue
            if not remaining:
                return source.with_edits([source.delete_statement(node)])
            return source.with_edits([Edit.from_node(node, ImportStatement(symbol.module, tuple(remaining)).render())])

        return source


class MemberTransform(abc.ABC):
    """A change to the accesses of a member, applied by :class:`~flama._upgrade.operations.Rewrite`."""

    @abc.abstractmethod
    def __call__(self, member: str, value: str | None, line: int) -> tuple[str | None, Todo | None]:
        """Replace an access to ``member``.

        :param member: Member as written, e.g. ``DependencyNotInstalled.Dependency``.
        :param value: Attribute picked out of the member (``Owner.Member.value``), or ``None`` when the member is
            used as a whole.
        :param line: Line of the access.
        :return: Source replacing the access, or ``None`` to leave it, and an optional follow-up.
        """
        ...


@dataclasses.dataclass(frozen=True)
class MapValue(MemberTransform):
    """Replace a value picked out of a member with the literal that now stands for it.

    Rewrites ``Owner.Member.value`` into ``"<literal>"``. Values the mapping does not cover, and uses of the member
    other than picking a value, emit a follow-up.

    :param values: Value name to the literal that replaces it.
    :param note: Follow-up message for uses the mapping does not cover.
    """

    values: t.Mapping[str, str]
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _frozen(self.values))

    def __call__(self, member: str, value: str | None, line: int) -> tuple[str | None, Todo | None]:
        literal = dict(self.values).get(value) if value is not None else None
        if literal is None:
            written = member if value is None else f"{member}.{value}"
            return None, Todo(line, self.note or f"`{written}` was removed")

        return f'"{literal}"', None
