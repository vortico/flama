import dataclasses
import difflib
import pathlib

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from flama._cli.formatting import CONSOLE
from flama.upgrade.operations import Todo

__all__ = ["FileReport", "Report"]


@dataclasses.dataclass(frozen=True)
class FileReport:
    """Per-file outcome of a migration run.

    :param path: File the report refers to.
    :param original: Source before the migration.
    :param updated: Source after the migration.
    :param todos: Manual follow-ups emitted for this file.
    :param changed: Whether the migration produced any edit.
    """

    path: pathlib.Path
    original: str
    updated: str
    todos: tuple[Todo, ...]
    changed: bool


class Report:
    """Aggregated result of a migration run, with Rich rendering for the CLI.

    :param target: Target version the run upgraded to.
    """

    def __init__(self, target: str) -> None:
        self.target = target
        self.files: list[FileReport] = []
        self.skipped: list[pathlib.Path] = []

    def add(self, file_report: FileReport) -> None:
        """Record a per-file outcome."""
        self.files.append(file_report)

    def add_skipped(self, path: pathlib.Path) -> None:
        """Record a file skipped because it could not be parsed."""
        self.skipped.append(path)

    @property
    def changed(self) -> list[FileReport]:
        """Files the migration modified."""
        return [file_report for file_report in self.files if file_report.changed]

    @property
    def todos(self) -> list[tuple[pathlib.Path, Todo]]:
        """All manual follow-ups across files, paired with their file path."""
        return [(file_report.path, todo) for file_report in self.files for todo in file_report.todos]

    def render(self, console: Console = CONSOLE, *, diff: bool = True) -> None:
        """Render the run to ``console``.

        :param console: Console to print to.
        :param diff: When ``True`` print a unified diff per changed file (dry-run); otherwise only the
            summary and follow-ups are shown (write mode).
        """
        if diff:
            for file_report in self.changed:
                console.print(self._diff(file_report))

        summary = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        summary.add_row("Scanned", str(len(self.files)))
        summary.add_row("Changed", str(len(self.changed)))
        if self.skipped:
            summary.add_row("Skipped (parse errors)", str(len(self.skipped)))
        console.print(
            Panel(
                summary,
                title=f"Flama upgrade to {self.target}",
                title_align="left",
                border_style="accent",
                padding=(0, 1),
            )
        )

        if self.todos:
            console.print(
                Panel(
                    self._follow_ups(),
                    title="Manual follow-ups",
                    title_align="left",
                    border_style="warning",
                    padding=(0, 1),
                )
            )

    def _diff(self, file_report: FileReport) -> Text:
        text = Text()
        lines = difflib.unified_diff(
            file_report.original.splitlines(keepends=True),
            file_report.updated.splitlines(keepends=True),
            fromfile=str(file_report.path),
            tofile=str(file_report.path),
        )
        for line in lines:
            text.append(line, style=self._diff_style(line))
            if not line.endswith("\n"):
                text.append("\n")
        return text

    @staticmethod
    def _diff_style(line: str) -> str:
        if line.startswith(("+++", "---")):
            return "heading"
        if line.startswith("@@"):
            return "info"
        if line.startswith("+"):
            return "success"
        if line.startswith("-"):
            return "error"
        return "description"

    def _follow_ups(self) -> Text:
        body = Text()
        for index, (path, todo) in enumerate(self.todos):
            if index:
                body.append("\n")
            body.append(f"{path}:{todo.line}", style="warning")
            body.append(f"  {todo.message}", style="description")
        return body
