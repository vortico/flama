import io
import pathlib
from unittest.mock import patch

import pytest
from rich.console import Console

from flama._cli.formatting import FLAMA_THEME
from flama._upgrade.migration import Migration
from flama._upgrade.operations import MoveModule
from flama._upgrade.runner import discover, run


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

    @pytest.fixture(scope="function")
    def migrations(self) -> tuple[Migration, ...]:
        return (
            Migration(target="2.0", source=">=1.0,<2.0", operations=(MoveModule("a", "b"),)),
            Migration(target="3.0", source=">=2.0,<3.0", operations=(MoveModule("b", "c"),)),
        )

    @pytest.mark.parametrize(
        ["write", "expected"],
        [
            pytest.param(False, "from flama.validation import X\n", id="diff_leaves_file"),
            pytest.param(True, "from flama.schemas.components import X\n", id="write_rewrites_file"),
        ],
    )
    def test_write_mode(self, tmp_path: pathlib.Path, console: Console, write: bool, expected: str) -> None:
        path = tmp_path / "a.py"
        path.write_text("from flama.validation import X\n")

        report = run([tmp_path], write=write, console=console)

        assert path.read_text() == expected
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

    @pytest.mark.parametrize(
        ["source", "expected", "target"],
        [
            pytest.param(None, "from c import X\n", "3.0", id="whole_chain"),
            pytest.param("2.0", "from a import X\n", "3.0", id="source_narrows_chain"),
            pytest.param("9.9", "from a import X\n", "3.0", id="nothing_to_do"),
        ],
    )
    def test_chain(
        self,
        tmp_path: pathlib.Path,
        console: Console,
        migrations: tuple[Migration, ...],
        source,
        expected: str,
        target: str,
    ) -> None:
        path = tmp_path / "a.py"
        path.write_text("from a import X\n")

        with patch("flama._upgrade.runner.MIGRATIONS", migrations):
            report = run([tmp_path], source=source, write=True, console=console)

        assert path.read_text() == expected
        assert report.target == target
