import pathlib

import pytest
from click.testing import CliRunner

from flama._cli.commands.upgrade import command


class TestCaseCommand:
    def test_diff_exits_with_error_when_changes(self, runner: CliRunner, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.py"
        path.write_text("from flama.validation import X\n")

        result = runner.invoke(command, [str(path)])

        assert result.exit_code == 1, result.output
        assert path.read_text() == "from flama.validation import X\n"

    def test_write_applies_and_exits_zero(self, runner: CliRunner, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.py"
        path.write_text("from flama.validation import X\n")

        result = runner.invoke(command, [str(path), "--write"])

        assert result.exit_code == 0, result.output
        assert path.read_text() == "from flama.schemas.components import X\n"

    def test_no_changes_exits_zero(self, runner: CliRunner, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.py"
        path.write_text("x = 1\n")

        result = runner.invoke(command, [str(path)])

        assert result.exit_code == 0, result.output

    def test_requires_paths(self, runner: CliRunner) -> None:
        result = runner.invoke(command, [])

        assert result.exit_code != 0

    @pytest.mark.parametrize(
        ["args", "expected"],
        [
            pytest.param(
                ["--select", "move-module:flama.validation"],
                "from flama.schemas.components import X\n",
                id="select_match",
            ),
            pytest.param(
                ["--skip", "move-module:flama.validation"],
                "from flama.validation import X\n",
                id="skip_match",
            ),
        ],
    )
    def test_select_and_skip(self, runner: CliRunner, tmp_path: pathlib.Path, args: list[str], expected: str) -> None:
        path = tmp_path / "a.py"
        path.write_text("from flama.validation import X\n")

        result = runner.invoke(command, [str(path), "--write", *args])

        assert result.exit_code == 0, result.output
        assert path.read_text() == expected
