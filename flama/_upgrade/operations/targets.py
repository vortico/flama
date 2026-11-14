import ast
import dataclasses
import typing as t

from flama._upgrade.source import Source

__all__ = ["Target", "Module", "Symbol", "Call", "Method", "Member"]


@dataclasses.dataclass(frozen=True)
class Module:
    """A module, matched through the statements that import it.

    :param path: Fully-qualified module path.
    """

    kind: t.ClassVar[str] = "module"

    path: str

    @property
    def dotted(self) -> str:
        return self.path


@dataclasses.dataclass(frozen=True)
class Symbol:
    """A symbol of a module, matched through its imports and the references to it.

    :param module: Fully-qualified module path the symbol belongs to.
    :param name: Symbol name.
    """

    kind: t.ClassVar[str] = "symbol"

    module: str
    name: str

    @property
    def dotted(self) -> str:
        return f"{self.module}.{self.name}"


@dataclasses.dataclass(frozen=True)
class Call:
    """The calls to a symbol, whether through the name it was imported as or through its module.

    :param symbol: Callee.
    :param with_arguments: Only match calls passing at least one argument.
    """

    kind: t.ClassVar[str] = "call"

    symbol: Symbol
    with_arguments: bool = False

    @property
    def dotted(self) -> str:
        return self.symbol.dotted

    def calls(self, source: Source) -> list[ast.Call]:
        """The calls this target matches in ``source``."""
        callees = {id(node) for node in source.symbol_references(self.symbol.module, self.symbol.name)}
        return [
            node
            for node in ast.walk(source.tree)
            if isinstance(node, ast.Call)
            and id(node.func) in callees
            and (not self.with_arguments or node.args or node.keywords)
        ]


@dataclasses.dataclass(frozen=True)
class Method:
    """The calls to a method, whatever object it is called on (``obj.name(...)``).

    The object's type cannot be known from the source alone, so calls are matched by the method's name, which suits
    names distinctive enough not to belong to unrelated APIs.

    :param name: Method name.
    """

    kind: t.ClassVar[str] = "method"

    name: str

    @property
    def dotted(self) -> str:
        return self.name

    def calls(self, source: Source) -> list[ast.Call]:
        """The calls this target matches in ``source``."""
        return [
            node
            for node in ast.walk(source.tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == self.name
        ]


@dataclasses.dataclass(frozen=True)
class Member:
    """The accesses to an attribute of a symbol (``Symbol.name``).

    :param symbol: Owner of the attribute.
    :param name: Attribute name.
    """

    kind: t.ClassVar[str] = "member"

    symbol: Symbol
    name: str

    @property
    def dotted(self) -> str:
        return f"{self.symbol.dotted}.{self.name}"


Target: t.TypeAlias = Module | Symbol | Call | Method | Member
