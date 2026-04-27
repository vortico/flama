import importlib.metadata
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from rich.panel import Panel
from rich.text import Text

from flama._cli.formatting import (
    CONSOLE,
    FlamaCommand,
    FlamaContext,
    FlamaGroup,
    RichHelpFormatter,
    _get_version,
    _render_error,
    _render_help,
)


class TestCaseGetVersion:
    @pytest.mark.parametrize(
        ["installed", "expected"],
        [
            pytest.param(True, "1.2.3", id="installed"),
            pytest.param(False, "dev", id="not_installed"),
        ],
    )
    def test__get_version(self, installed: bool, expected: str) -> None:
        if installed:
            with patch("flama._cli.formatting.importlib.metadata.version", return_value="1.2.3"):
                assert _get_version() == expected
        else:
            with patch(
                "flama._cli.formatting.importlib.metadata.version",
                side_effect=importlib.metadata.PackageNotFoundError,
            ):
                assert _get_version() == expected


class TestCaseRichHelpFormatter:
    @pytest.fixture(scope="function")
    def formatter(self) -> RichHelpFormatter:
        return RichHelpFormatter()

    def test_init(self, formatter: RichHelpFormatter) -> None:
        assert formatter._sections == []

    @pytest.mark.parametrize(
        ["string", "appended"],
        [
            pytest.param("hello", True, id="non_empty"),
            pytest.param("   ", False, id="whitespace_only"),
            pytest.param("", False, id="empty"),
        ],
    )
    def test_write(self, formatter: RichHelpFormatter, string: str, appended: bool) -> None:
        formatter.write(string)

        assert (len(formatter._sections) == 1) is appended

    def test_write_usage(self, formatter: RichHelpFormatter) -> None:
        formatter.write_usage("flama", args="[OPTIONS]")

        assert len(formatter._sections) == 1
        assert isinstance(formatter._sections[0], Text)

    def test_write_heading(self, formatter: RichHelpFormatter) -> None:
        formatter.write_heading("Commands")

        assert formatter._current_heading == "Commands"

    def test_write_paragraph(self, formatter: RichHelpFormatter) -> None:
        formatter.write_paragraph()

        assert formatter._sections == []

    def test_write_dl(self, formatter: RichHelpFormatter) -> None:
        formatter._current_heading = "Options"
        formatter.write_dl([("--foo", "Foo option"), ("--bar", "Bar option")])

        assert len(formatter._sections) == 1
        assert isinstance(formatter._sections[0], Panel)

    def test_render(self, formatter: RichHelpFormatter) -> None:
        formatter.write_usage("flama", args="[OPTIONS]")
        formatter.write("Hello")
        console = MagicMock()

        formatter.render(console)

        assert console.print.call_count == 2

    def test_getvalue(self, formatter: RichHelpFormatter) -> None:
        formatter.write_usage("flama")

        result = formatter.getvalue()

        assert isinstance(result, str)
        assert "flama" in result


class TestCaseFlamaContext:
    def test_formatter_class(self) -> None:
        assert FlamaContext.formatter_class is RichHelpFormatter


class TestCaseFlamaCommand:
    def test_context_class(self) -> None:
        assert FlamaCommand.context_class is FlamaContext


class TestCaseFlamaGroup:
    @pytest.fixture(scope="function")
    def group(self) -> click.Group:
        @click.group(cls=FlamaGroup)
        def cli() -> None:
            pass

        @cli.command()
        def sub() -> None:
            click.echo("ok")

        return cli

    def test_init(self) -> None:
        assert FlamaGroup.context_class is FlamaContext
        assert FlamaGroup.command_class is FlamaCommand

    def test_format_help(self, group: click.Group) -> None:
        ctx = click.Context(group)
        formatter = RichHelpFormatter()

        group.format_help(ctx, formatter)

        assert len(formatter._sections) > 0
        first = formatter._sections[0]
        assert isinstance(first, Text)
        assert "Flama" in str(first)

    @pytest.mark.parametrize(
        ["scenario", "args", "expected_exit_code"],
        [
            pytest.param("no_args_help", [], 0, id="no_args_help"),
            pytest.param("usage_error", ["--unknown-flag"], 2, id="usage_error"),
            pytest.param("ok", ["sub"], 0, id="ok"),
        ],
    )
    def test_main(
        self,
        runner: CliRunner,
        group: click.Group,
        scenario: str,
        args: list[str],
        expected_exit_code: int,
    ) -> None:
        result = runner.invoke(group, args)

        assert result.exit_code == expected_exit_code, result.output


class TestCaseRenderHelp:
    def test__render_help(self) -> None:
        @click.group(cls=FlamaGroup)
        def cli() -> None:
            pass

        ctx = FlamaContext(cli)

        with patch.object(CONSOLE, "print") as mock_print:
            _render_help(ctx)

        assert mock_print.called


class TestCaseRenderError:
    @pytest.mark.parametrize(
        "with_ctx",
        [
            pytest.param(True, id="with_ctx"),
            pytest.param(False, id="no_ctx"),
        ],
    )
    def test__render_error(self, with_ctx: bool) -> None:
        ctx: click.Context | None = None
        if with_ctx:

            @click.group(cls=FlamaGroup)
            def cli() -> None:
                pass

            ctx = click.Context(cli)

        with patch.object(CONSOLE, "print") as mock_print:
            _render_error("oops", ctx=ctx)

        mock_print.assert_called_once()
        panel = mock_print.call_args.args[0]
        assert isinstance(panel, Panel)
