from pathlib import Path
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from flama._cli.config.app import App, DictApp, FlamaApp, Model, StrApp, _AppContext, options


class TestCaseAppContext:
    @pytest.mark.parametrize(
        ["app", "module", "expected"],
        [
            pytest.param("var", "mod", "mod:var", id="string_app"),
            pytest.param(MagicMock(), None, None, id="asgi_app"),
        ],
    )
    def test_app(self, app: object, module: str | None, expected: str | None) -> None:
        ctx = _AppContext(app=app, path=Path("/tmp"), module=module)  # ty: ignore[invalid-argument-type]

        if expected is None:
            assert ctx.app is app
        else:
            assert ctx.app == expected

    def test_dir(self) -> None:
        ctx = _AppContext(app="app", path=Path("/tmp/abc"))

        assert ctx.dir == "/tmp/abc"


class TestCaseModel:
    def test_init(self) -> None:
        m = Model(url="/u", path="m.flm", name="my-model")

        assert m.url == "/u"
        assert m.path == "m.flm"
        assert m.name == "my-model"


class TestCaseApp:
    @pytest.mark.parametrize(
        ["input_app", "expected_class"],
        [
            pytest.param("module:app", StrApp, id="string"),
            pytest.param({"title": "MyApp"}, DictApp, id="dict"),
            pytest.param(MagicMock(), FlamaApp, id="asgi_app"),
        ],
    )
    def test_build(self, input_app: object, expected_class: type[App]) -> None:
        result = App.build(input_app)  # ty: ignore[invalid-argument-type]

        assert isinstance(result, expected_class)


class TestCaseFlamaApp:
    def test_context(self) -> None:
        asgi_app = MagicMock()
        flama_app = FlamaApp(app=asgi_app)

        with flama_app.context as ctx:
            assert ctx.app is asgi_app
            assert isinstance(ctx.dir, str)


class TestCaseDictApp:
    def test_init(self) -> None:
        d = DictApp()

        assert d.title == "Flama"
        assert d.debug is False
        assert d.version == "0.1.0"
        assert len(d.models) == 1

    def test_from_dict(self) -> None:
        data = {
            "title": "MyApp",
            "models": [{"url": "/u", "path": "m.flm", "name": "n"}],
        }

        d = DictApp.from_dict(data)

        assert isinstance(d, DictApp)
        assert d.title == "MyApp"
        assert len(d.models) == 1
        assert isinstance(d.models[0], Model)
        assert d.models[0].name == "n"

    def test_context(self) -> None:
        d = DictApp(title="MyApp")

        with d.context as ctx:
            assert isinstance(ctx.dir, str)
            assert Path(ctx.dir).is_dir()
            assert isinstance(ctx.app, str)
            assert ctx.app.endswith(":app")


class TestCaseStrApp:
    def test_context(self) -> None:
        s = StrApp("module.path:app_var")

        with s.context as ctx:
            assert ctx.app == "module.path:app_var"


class TestCaseOptions:
    def test_options(self, runner: CliRunner) -> None:
        @click.command()
        @options
        def cmd(app: DictApp) -> None:
            click.echo(f"title={app.title}")
            click.echo(f"path={app.models[0].path}")
            click.echo(f"url={app.models[0].url}")
            click.echo(f"name={app.models[0].name}")
            click.echo(f"count={len(app.models)}")

        result = runner.invoke(cmd, ["--model", "m.flm", "/m/", "m", "--app-title", "MyApp"])

        assert result.exit_code == 0, result.output
        assert "title=MyApp" in result.output
        assert "path=m.flm" in result.output
        assert "url=/m/" in result.output
        assert "name=m" in result.output
        assert "count=1" in result.output

    def test_options_multiple_models(self, runner: CliRunner) -> None:
        @click.command()
        @options
        def cmd(app: DictApp) -> None:
            click.echo(f"count={len(app.models)}")
            for m in app.models:
                click.echo(f"{m.path}|{m.url}|{m.name}")

        result = runner.invoke(
            cmd,
            ["--model", "m1.flm", "/m1/", "m1", "--model", "m2.flm", "/m2/", "m2"],
        )

        assert result.exit_code == 0, result.output
        assert "count=2" in result.output
        assert "m1.flm|/m1/|m1" in result.output
        assert "m2.flm|/m2/|m2" in result.output
