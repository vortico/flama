import abc
import ast
import dataclasses
import typing as t

from flama._upgrade.operations._base import ApplyResult, Operation, Todo
from flama._upgrade.source import Edit, ImportStatement, Keyword, Source

__all__ = ["CallOperation", "UnwrapCall", "KeywordToPositional"]


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


@dataclasses.dataclass(frozen=True)
class CallOperation(Operation):
    """Base for operations that rewrite calls to a symbol imported from a module.

    Resolves the local binding for ``name`` imported from ``module`` (no-op when it is not imported), finds
    every ``name(...)`` call whose callee is that bare name, and delegates each one to :meth:`_rewrite`,
    which returns an optional :class:`Edit` and/or :class:`Todo`. Subclasses may narrow the matched calls
    through :meth:`_select` and post-process the rewritten source through :meth:`_finalize`.

    :param module: Module the callee is imported from.
    :param name: Callee symbol name in the source version.
    """

    module: str
    name: str

    def _select(self, calls: list[ast.Call]) -> list[ast.Call]:
        """Narrow the matched calls before rewriting (default: keep all)."""
        return calls

    @abc.abstractmethod
    def _rewrite(self, node: ast.Call, text: str) -> tuple[Edit | None, Todo | None]:
        """Produce the edit and/or follow-up for a single matched call."""
        ...

    def _finalize(self, source: Source, binding: str) -> Source:
        """Post-process the rewritten source once all edits are applied (default: unchanged)."""
        return source

    def apply(self, source: Source) -> ApplyResult:
        binding = source.local_binding(self.module, self.name)
        if binding is None:
            return ApplyResult(source, False)

        calls = self._select(
            [
                node
                for node in ast.walk(source.tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == binding
            ]
        )

        text = source.text
        edits: list[Edit] = []
        todos: list[Todo] = []
        for node in calls:
            edit, todo = self._rewrite(node, text)
            if edit is not None:
                edits.append(edit)
            if todo is not None:
                todos.append(todo)

        if not edits:
            return ApplyResult(source, False, tuple(todos))

        return ApplyResult(self._finalize(source.with_edits(edits), binding), True, tuple(todos))


@dataclasses.dataclass(frozen=True)
class UnwrapCall(CallOperation):
    """Unwrap ``Wrapper(inner, *rest, **kwargs)`` calls into ``inner(*rest, **kwargs)``.

    Rewrites matched calls so the first positional argument becomes the callee. This migrates the v1
    middleware pattern (``Middleware(SomeMiddleware, **options)``) to the v2 one
    (``SomeMiddleware(**options)``). When the wrapper name is no longer referenced afterwards (e.g. it is
    not also used as a base class), its import is removed. Each rewritten call emits a follow-up because the
    wrapped object may itself need changes.

    :param module: Module the wrapper is imported from.
    :param name: Wrapper symbol name.
    :param note: Follow-up message, prefixed with the unwrapped callee.
    """

    note: str

    @property
    def id(self) -> str:
        return f"unwrap-call:{self.module}:{self.name}"

    def _select(self, calls: list[ast.Call]) -> list[ast.Call]:
        return _drop_nested([node for node in calls if node.args])

    def _rewrite(self, node: ast.Call, text: str) -> tuple[Edit | None, Todo | None]:
        first = node.args[0]
        if isinstance(first, ast.Starred):
            return None, Todo(node.lineno, f"`{self.name}(...)` wraps a starred argument; unwrap it manually")
        inner = t.cast(str, ast.get_source_segment(text, first))
        parts = [t.cast(str, ast.get_source_segment(text, arg)) for arg in node.args[1:]]
        parts += [Keyword.from_node(text, keyword).render() for keyword in node.keywords]
        return Edit.from_node(node, f"{inner}({', '.join(parts)})"), Todo(node.lineno, f"`{inner}` {self.note}")

    def _finalize(self, source: Source, binding: str) -> Source:
        if any(isinstance(node, ast.Name) and node.id == binding for node in ast.walk(source.tree)):
            return source
        import_edit = self._remove_binding(source, binding)
        return source.with_edits([import_edit]) if import_edit is not None else source

    def _remove_binding(self, source: Source, binding: str) -> Edit | None:
        for node in source.imports:
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != self.module:
                continue
            remaining = [(alias.name, alias.asname) for alias in node.names if (alias.asname or alias.name) != binding]
            if len(remaining) == len(node.names):
                continue
            if not remaining:
                return source.delete_statement(node)
            return Edit.from_node(node, ImportStatement(self.module, tuple(remaining)).render())
        return None


@dataclasses.dataclass(frozen=True)
class KeywordToPositional(CallOperation):
    """Move a keyword argument to the first positional position on a constructor call.

    When a matched call passes ``keyword`` as a keyword argument it is rewritten as the first positional
    argument (``Resp(content=x, ...)`` -> ``Resp(x, ...)``), matching v2 responses where ``content`` became
    positional-only. When the call passes neither a positional argument, ``keyword``, any of
    ``alternatives`` nor ``**kwargs``, a follow-up is emitted because the argument is now required.

    :param module: Module the callee is imported from.
    :param name: Callee symbol name.
    :param keyword: Keyword argument to promote to positional.
    :param alternatives: Other keyword names that also satisfy the requirement (e.g. ``path``).
    :param note: Follow-up message for calls that provide none of the accepted arguments.
    """

    keyword: str = "content"
    alternatives: tuple[str, ...] = ()
    note: str = ""

    @property
    def id(self) -> str:
        return f"keyword-to-positional:{self.module}:{self.name}:{self.keyword}"

    def _rewrite(self, node: ast.Call, text: str) -> tuple[Edit | None, Todo | None]:
        match = next((keyword for keyword in node.keywords if keyword.arg == self.keyword), None)
        if match is not None:
            func = t.cast(str, ast.get_source_segment(text, node.func))
            parts = [t.cast(str, ast.get_source_segment(text, match.value))]
            parts += [t.cast(str, ast.get_source_segment(text, arg)) for arg in node.args]
            parts += [Keyword.from_node(text, keyword).render() for keyword in node.keywords if keyword is not match]
            return Edit.from_node(node, f"{func}({', '.join(parts)})"), None
        if not node.args and not any(
            keyword.arg in self.alternatives or keyword.arg is None for keyword in node.keywords
        ):
            return None, Todo(node.lineno, self.note or f"`{self.name}(...)` now requires `{self.keyword}`")
        return None, None
