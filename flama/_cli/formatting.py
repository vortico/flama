import importlib.metadata
import typing as t

import click
from click.exceptions import NoArgsIsHelpError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

__all__ = ["CONSOLE", "FLAMA_THEME", "FlamaCommand", "FlamaContext", "FlamaGroup"]

FLAMA_THEME = Theme(
    {
        "flama": "bold #e25822",
        "heading": "bold #e25822",
        "command": "bold #fa7754",
        "accent": "#008080",
        "metavar": "#656775",
        "description": "#a5a6b1",
        "error": "bold #e25822",
        "success": "bold #00976e",
        "info": "#00bbd5",
        "warning": "#9e744f",
    }
)

CONSOLE = Console(theme=FLAMA_THEME)


def _get_version() -> str:
    try:
        return importlib.metadata.version("flama")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "dev"


class RichHelpFormatter(click.HelpFormatter):
    """A :class:`click.HelpFormatter` that captures usage / sections for Rich rendering."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self._sections: list[Text | Panel | Table | str] = []

    def write(self, string: str) -> None:
        if string.strip():
            self._sections.append(Text(string.rstrip()))

    def write_usage(self, prog: str, args: str = "", prefix: str | None = None) -> None:
        usage = Text()
        usage.append("Usage: ", style="heading")
        usage.append(prog, style="command")
        if args:
            usage.append(f" {args}", style="metavar")
        self._sections.append(usage)

    def write_heading(self, heading: str) -> None:
        self._current_heading = heading

    def write_paragraph(self) -> None:
        pass

    def write_dl(self, rows: t.Sequence[tuple[str, str]], col_max: int = 30, col_spacing: int = 2) -> None:
        heading = getattr(self, "_current_heading", "")

        table = Table(show_header=False, box=None, padding=(0, 2, 0, 2), expand=True)
        table.add_column(style="command", no_wrap=True, min_width=12)
        table.add_column(style="description")
        for name, help_text in rows:
            table.add_row(name, help_text)

        panel = Panel(table, title=heading, title_align="left", border_style="accent", padding=(0, 1))
        self._sections.append(panel)

    def render(self, target: Console | None = None) -> None:
        con = target or CONSOLE
        for section in self._sections:
            if isinstance(section, str):
                con.print(section, highlight=False)
            else:
                con.print(section)

    def getvalue(self) -> str:
        with CONSOLE.capture() as capture:
            self.render()
        return capture.get()


class FlamaContext(click.Context):
    """Click context wired to the :class:`RichHelpFormatter` for rich help/error rendering."""

    formatter_class = RichHelpFormatter


class FlamaCommand(click.Command):
    """Click command using :class:`FlamaContext` so help and errors render with the Flama theme."""

    context_class = FlamaContext


class FlamaGroup(click.Group):
    """Click group rendering a Flama-themed banner on help and panelled errors on usage failures."""

    context_class = FlamaContext
    command_class = FlamaCommand
    group_class = type

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if isinstance(formatter, RichHelpFormatter):
            banner = Text()
            banner.append(" 🔥 Flama", style="flama")
            banner.append(f" v{_get_version()}", style="description")
            formatter._sections.append(banner)
            formatter._sections.append(Text(""))

        super().format_help(ctx, formatter)

    def main(self, *args: t.Any, standalone_mode: bool = True, **kwargs: t.Any) -> t.Any:
        try:
            return super().main(*args, standalone_mode=False, **kwargs)
        except NoArgsIsHelpError as e:
            _render_help(e.ctx)
            raise SystemExit(0) if standalone_mode else e  # noqa: B904
        except click.UsageError as e:
            _render_error(e.format_message(), ctx=e.ctx)
            raise SystemExit(2) if standalone_mode else e  # noqa: B904
        except click.ClickException as e:
            _render_error(e.format_message())
            raise SystemExit(e.exit_code) if standalone_mode else e  # noqa: B904
        except SystemExit:
            raise


def _render_help(ctx: click.Context) -> None:
    formatter = ctx.make_formatter()
    ctx.command.format_help(ctx, formatter)
    if isinstance(formatter, RichHelpFormatter):
        formatter.render()
    else:  # pragma: no cover
        click.echo(formatter.getvalue(), color=ctx.color)


def _render_error(message: str, *, ctx: click.Context | None = None) -> None:
    body = Text()
    if ctx:
        pieces = ctx.command.collect_usage_pieces(ctx)
        body.append("Usage: ", style="heading")
        body.append(f"{ctx.command_path} {' '.join(pieces)}", style="metavar")
        body.append("\n\n")
    body.append(message, style="error")
    CONSOLE.print(Panel(body, title="Error", title_align="left", border_style="error", padding=(0, 1)))
