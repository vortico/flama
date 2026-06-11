import ast
import dataclasses
import pathlib
import typing as t

__all__ = ["Edit", "ImportStatement", "Keyword", "Source"]


@dataclasses.dataclass(frozen=True)
class Edit:
    """A single text replacement expressed in source coordinates.

    Coordinates follow :mod:`ast` conventions: line numbers are 1-based and column offsets are 0-based
    UTF-8 byte offsets. The span ``[start, end)`` is replaced verbatim by :attr:`text`, leaving the
    surrounding source untouched.

    :param start_line: 1-based line where the replacement begins.
    :param start_col: 0-based byte column where the replacement begins.
    :param end_line: 1-based line where the replacement ends.
    :param end_col: 0-based byte column where the replacement ends.
    :param text: Replacement text (may contain newlines).
    """

    start_line: int
    start_col: int
    end_line: int
    end_col: int
    text: str

    @classmethod
    def from_node(cls, node: ast.stmt | ast.expr, text: str) -> "Edit":
        """Build an edit covering the full span of ``node``, replaced by ``text``.

        :param node: AST node whose source span is replaced.
        :param text: Replacement text.
        :return: An edit covering ``node``.
        """
        return cls(node.lineno, node.col_offset, t.cast(int, node.end_lineno), t.cast(int, node.end_col_offset), text)


@dataclasses.dataclass(frozen=True)
class ImportStatement:
    """A renderable ``import`` / ``from ... import`` statement.

    :param module: Module for a ``from`` import, or ``None`` for a plain ``import``.
    :param aliases: ``(name, asname)`` pairs imported by the statement.
    """

    module: str | None
    aliases: tuple[tuple[str, str | None], ...]

    def render(self) -> str:
        """Render the statement back to source."""
        names = ", ".join(name if asname is None else f"{name} as {asname}" for name, asname in self.aliases)
        return f"from {self.module} import {names}" if self.module is not None else f"import {names}"


@dataclasses.dataclass(frozen=True)
class Keyword:
    """A renderable call argument (``name=value``, or ``**value`` when :attr:`arg` is ``None``).

    :param arg: Keyword name, or ``None`` for a ``**value`` unpacking.
    :param value: Source of the argument value.
    """

    arg: str | None
    value: str

    @classmethod
    def from_node(cls, text: str, keyword: ast.keyword) -> "Keyword":
        """Build a keyword from an :class:`ast.keyword` node, reading its value segment from ``text``."""
        return cls(keyword.arg, t.cast(str, ast.get_source_segment(text, keyword.value)))

    def render(self) -> str:
        """Render the argument back to source."""
        return f"**{self.value}" if self.arg is None else f"{self.arg}={self.value}"


class _BindingFinder(ast.NodeVisitor):
    """Detects whether a name is bound by anything other than a plain import.

    A name is considered rebound when it is assigned, used as a function/lambda parameter, used as the
    name of a function or class definition, or declared ``global``/``nonlocal``. Import aliases are
    intentionally ignored: they are the expected binding for a symbol an operation is about to rewrite.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.found = False

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store) and node.id == self.name:
            self.found = True

    def visit_arg(self, node: ast.arg) -> None:
        if node.arg == self.name:
            self.found = True

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == self.name:
            self.found = True
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name == self.name:
            self.found = True
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == self.name:
            self.found = True
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        if self.name in node.names:
            self.found = True

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        if self.name in node.names:
            self.found = True


class Source:
    """An immutable view over a single Python source file and its parsed syntax tree.

    A :class:`Source` is the unit every :class:`~flama._upgrade.operations.Operation` works on. It exposes
    the import statements and name references an operation needs to inspect, a conservative shadowing
    check, and an offset-based splicer that rewrites only the spans an operation targets while preserving
    the rest of the file byte-for-byte.

    :param path: Path the source was read from (used for reporting only).
    :param text: Full source text.
    :param tree: Parsed module for ``text``.
    """

    def __init__(self, path: pathlib.Path, text: str, tree: ast.Module) -> None:
        self.path = path
        self.text = text
        self.tree = tree

    @classmethod
    def parse(cls, path: pathlib.Path, text: str) -> "Source":
        """Parse ``text`` into a :class:`Source`.

        :param path: Path the source was read from.
        :param text: Full source text.
        :return: The parsed source.
        :raises SyntaxError: If ``text`` is not valid Python.
        """
        return cls(path, text, ast.parse(text))

    @property
    def imports(self) -> list[ast.Import | ast.ImportFrom]:
        """Every ``import`` and ``from ... import`` statement in the module, in tree order."""
        return [node for node in ast.walk(self.tree) if isinstance(node, (ast.Import, ast.ImportFrom))]

    def references(self, name: str) -> list[ast.Name]:
        """Return every bare-name reference to ``name`` (``ast.Name`` nodes).

        Attribute accesses (``obj.name``) are ``ast.Attribute`` nodes and are deliberately excluded, so
        renaming references never touches an unrelated attribute that happens to share the name.

        :param name: Identifier to search for.
        :return: Matching name nodes.
        """
        return [node for node in ast.walk(self.tree) if isinstance(node, ast.Name) and node.id == name]

    def is_rebound(self, name: str) -> bool:
        """Return ``True`` if ``name`` is shadowed or reassigned anywhere in the module.

        When a name is rebound, renaming its references cannot be done safely from imports alone, so the
        caller should fall back to a manual follow-up instead of risking an incorrect edit.

        :param name: Identifier to check.
        :return: Whether the name is bound by something other than an import alias.
        """
        finder = _BindingFinder(name)
        finder.visit(self.tree)
        return finder.found

    def local_binding(self, module: str, name: str) -> str | None:
        """Return the local name ``name`` is bound to when imported from ``module``.

        Only top-level ``from <module> import <name>`` statements are considered. The binding is the alias
        when one is present (``import X as Y`` -> ``Y``), otherwise the name itself. ``None`` is returned
        when the symbol is not imported from that module.

        :param module: Module the symbol is imported from.
        :param name: Symbol name to resolve.
        :return: The local binding, or ``None`` when not imported from ``module``.
        """
        for node in self.imports:
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == module:
                for alias in node.names:
                    if alias.name == name:
                        return alias.asname or alias.name
        return None

    def delete_statement(self, node: ast.stmt) -> Edit:
        """Build an edit that removes ``node``'s full lines, including the trailing newline.

        :param node: Statement to delete.
        :return: An edit that blanks the statement's span.
        """
        lines = self.text.splitlines(keepends=True)
        end_line = t.cast(int, node.end_lineno)
        end_col = len(lines[end_line - 1].encode("utf-8"))
        return Edit(node.lineno, 0, end_line, end_col, "")

    def with_edits(self, edits: t.Sequence[Edit]) -> "Source":
        """Return a new :class:`Source` with ``edits`` applied.

        Edits are applied bottom-to-top and right-to-left so that earlier coordinates remain valid as the
        text changes. Slicing is done on the UTF-8 encoded line to honour ``ast`` byte offsets. The result
        is re-parsed so subsequent operations observe the updated tree.

        :param edits: Non-overlapping edits to apply.
        :return: A new source reflecting the edits (unchanged when ``edits`` is empty).
        """
        if not edits:
            return self

        lines = self.text.splitlines(keepends=True)
        for edit in sorted(edits, key=lambda e: (e.start_line, e.start_col), reverse=True):
            prefix = lines[edit.start_line - 1].encode("utf-8")[: edit.start_col].decode("utf-8")
            suffix = lines[edit.end_line - 1].encode("utf-8")[edit.end_col :].decode("utf-8")
            lines[edit.start_line - 1 : edit.end_line] = [prefix + edit.text + suffix]

        return Source.parse(self.path, "".join(lines))
