import io
import pathlib

import pytest
from rich.console import Console

from flama._cli.formatting import FLAMA_THEME
from flama.upgrade.runner import discover, run


class TestCaseDiscover:
    def test_directory_recurses_and_filters(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.txt").write_text("nope\n")
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "c.py").write_text("y = 2\n")
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "d.py").write_text("z = 3\n")

        assert sorted(path.name for path in discover([tmp_path])) == ["a.py", "c.py"]

    def test_explicit_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.py"
        path.write_text("x = 1\n")

        assert discover([str(path)]) == [path]

    def test_deduplicates(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.py"
        path.write_text("x = 1\n")

        assert discover([str(path), str(path)]) == [path]


class TestCaseRun:
    @pytest.fixture(scope="function")
    def console(self) -> Console:
        return Console(file=io.StringIO(), width=200, theme=FLAMA_THEME)

    def test_diff_mode_does_not_write(self, tmp_path: pathlib.Path, console: Console) -> None:
        path = tmp_path / "a.py"
        path.write_text("from flama.validation import X\n")

        report = run([tmp_path], console=console)

        assert path.read_text() == "from flama.validation import X\n"
        assert len(report.changed) == 1

    def test_write_mode_rewrites(self, tmp_path: pathlib.Path, console: Console) -> None:
        path = tmp_path / "a.py"
        path.write_text("from flama.validation import X\n")

        report = run([tmp_path], write=True, console=console)

        assert path.read_text() == "from flama.schemas.components import X\n"
        assert len(report.changed) == 1

    def test_skips_unparseable(self, tmp_path: pathlib.Path, console: Console) -> None:
        path = tmp_path / "a.py"
        path.write_text("def (:\n")

        report = run([tmp_path], console=console)

        assert report.skipped == [path]
        assert report.changed == []

    def test_skip_operation_leaves_file(self, tmp_path: pathlib.Path, console: Console) -> None:
        path = tmp_path / "a.py"
        path.write_text("from flama.validation import X\n")

        report = run([tmp_path], write=True, skip={"move-module:flama.validation"}, console=console)

        assert path.read_text() == "from flama.validation import X\n"
        assert report.changed == []
