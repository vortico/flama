import click

from flama._cli.formatting import FlamaCommand
from flama._upgrade import run as run_upgrade

__all__ = ["upgrade", "command"]


def _split(value: str | None) -> set[str] | None:
    """Parse a comma-separated option into a set of ids, or ``None`` when empty."""
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


@click.command(name="upgrade", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.argument("paths", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--to", "target", default=None, help="Target Flama version (default: latest known migration).")
@click.option("--from", "source", default=None, help="Source Flama version (default: detect installed).")
@click.option("--diff/--write", "diff_only", default=True, help="Preview a diff (default) or rewrite files in place.")
@click.option("--select", default=None, help="Comma-separated operation ids to run exclusively.")
@click.option("--skip", default=None, help="Comma-separated operation ids to skip.")
@click.pass_context
def command(
    ctx: click.Context,
    paths: tuple[str, ...],
    target: str | None,
    source: str | None,
    diff_only: bool,
    select: str | None,
    skip: str | None,
) -> None:
    """Upgrade a Flama codebase to a newer major version.

    Rewrite import statements and renamed symbols across the Python files under <PATHS> so they match the
    target Flama version. By default the command previews a unified diff and leaves files untouched; pass
    --write to apply the changes in place. Symbols that have no automatic replacement are flagged with a
    '# flama-upgrade' marker and listed as manual follow-ups.

    <PATHS> are the files and/or directories to process; directories are scanned recursively.

    \b
    Example:
        flama upgrade src/
        flama upgrade --write src/ tests/
        flama upgrade --to 2.0 --skip move-module:flama.asgi src/
    """
    report = run_upgrade(
        list(paths),
        target=target,
        source=source,
        write=not diff_only,
        select=_split(select),
        skip=_split(skip),
    )

    if diff_only and report.changed:
        ctx.exit(1)


upgrade = command.callback
