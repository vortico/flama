import io
import pathlib

import pytest
from rich.console import Console

from flama._cli.formatting import FLAMA_THEME
from flama._upgrade.operations import Todo
from flama._upgrade.report import FileReport, Report


class TestCaseReport:
    @pytest.fixture(scope="function")
    def console(self) -> Console:
        return Console(file=io.StringIO(), width=200, theme=FLAMA_THEME)

    def test_aggregates_changed_and_todos(self) -> None:
        report = Report("2.0")
        report.add(FileReport(pathlib.Path("a.py"), "x\n", "y\n", (Todo(2, "fix it"),), True))
        report.add(FileReport(pathlib.Path("b.py"), "x\n", "x\n", (), False))

        assert [file_report.path.name for file_report in report.changed] == ["a.py"]
        assert report.todos == [(pathlib.Path("a.py"), Todo(2, "fix it"))]

    def test_render_diff_and_summary(self, console: Console) -> None:
        report = Report("2.0")
        report.add(FileReport(pathlib.Path("a.py"), "keep\nfrom a import X\n", "keep\nfrom b import X\n", (), True))

        report.render(console, diff=True)
        output = console.file.getvalue()

        assert "--- a.py" in output
        assert "@@" in output
        assert "-from a import X" in output
        assert "+from b import X" in output
        assert " keep" in output
        assert "Scanned" in output
        assert "Changed" in output

    def test_render_diff_without_trailing_newline(self, console: Console) -> None:
        report = Report("2.0")
        report.add(FileReport(pathlib.Path("a.py"), "from a import X", "from b import X", (), True))

        report.render(console, diff=True)

        assert "-from a import X\n+from b import X\n" in console.file.getvalue()

    def test_render_write_mode_skips_diff(self, console: Console) -> None:
        report = Report("2.0")
        report.add(FileReport(pathlib.Path("a.py"), "from a import X\n", "from b import X\n", (), True))

        report.render(console, diff=False)
        output = console.file.getvalue()

        assert "-from a import X" not in output
        assert "Changed" in output

    def test_render_skipped(self, console: Console) -> None:
        report = Report("2.0")
        report.add_skipped(pathlib.Path("bad.py"))

        report.render(console, diff=True)

        assert "Skipped" in console.file.getvalue()

    def test_render_follow_ups(self, console: Console) -> None:
        report = Report("2.0")
        report.add(FileReport(pathlib.Path("a.py"), "x\n", "x\n", (Todo(3, "do thing"), Todo(7, "do other")), False))

        report.render(console, diff=False)
        output = console.file.getvalue()

        assert "Manual follow-ups" in output
        assert "a.py:3" in output
        assert "do thing" in output
        assert "a.py:7" in output
