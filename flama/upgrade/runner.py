import pathlib
import typing as t

from rich.console import Console

from flama._cli.formatting import CONSOLE
from flama.upgrade.codemods import MIGRATIONS
from flama.upgrade.migration import resolve
from flama.upgrade.report import FileReport, Report
from flama.upgrade.source import Source

__all__ = ["discover", "run"]

_IGNORED_DIRS: t.Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }
)


def discover(paths: t.Sequence[str | pathlib.Path]) -> list[pathlib.Path]:
    """Expand ``paths`` into the Python files to process.

    Directories are walked recursively for ``*.py`` files, skipping common virtualenv, cache and build
    directories. Explicit file paths are taken as-is when they have a ``.py`` suffix. The result is
    de-duplicated while preserving discovery order.

    :param paths: Files and/or directories to scan.
    :return: The ordered, de-duplicated list of Python files.
    """
    found: list[pathlib.Path] = []
    for raw in paths:
        path = pathlib.Path(raw)
        if path.is_dir():
            found.extend(p for p in sorted(path.rglob("*.py")) if _IGNORED_DIRS.isdisjoint(p.parts))
        elif path.suffix == ".py":
            found.append(path)

    return list(dict.fromkeys(found))


def run(
    paths: t.Sequence[str | pathlib.Path],
    *,
    target: str | None = None,
    source: str | None = None,
    write: bool = False,
    select: set[str] | None = None,
    skip: set[str] | None = None,
    console: Console = CONSOLE,
) -> Report:
    """Apply a migration to every Python file under ``paths`` and render the outcome.

    Files that fail to parse are skipped and recorded. In write mode changed files are rewritten in place;
    otherwise a unified diff is printed and the files are left untouched.

    :param paths: Files and/or directories to process.
    :param target: Target version; the latest registered migration is used when omitted.
    :param source: Source version (informational).
    :param write: When ``True`` rewrite files in place; otherwise preview a diff.
    :param select: When given, only operations whose id is in this set run.
    :param skip: Operations whose id is in this set are skipped.
    :param console: Console used for rendering.
    :return: The aggregated run report.
    """
    migration = resolve(MIGRATIONS, target=target, source=source)
    report = Report(migration.target)

    for path in discover(paths):
        text = path.read_text(encoding="utf-8")
        try:
            parsed = Source.parse(path, text)
        except SyntaxError:
            report.add_skipped(path)
            continue

        upgraded, todos, changed = migration.apply(parsed, select=select, skip=skip)
        report.add(FileReport(path, text, upgraded.text, tuple(todos), changed))
        if changed and write:
            path.write_text(upgraded.text, encoding="utf-8")

    report.render(console, diff=not write)
    return report
