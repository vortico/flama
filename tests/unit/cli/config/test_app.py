import json
from pathlib import Path
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from flama._cli.config.app import App, DictApp, FlamaApp, Model, StrApp, _AppContext, _ModelSpec, _parse_params, options


class TestCaseAppContext:
    @pytest.mark.parametrize(
        ["app", "module", "is_asgi", "expected_str"],
        [
            pytest.param("var", "mod", False, "mod:var", id="string_with_module"),
            pytest.param(None, None, True, None, id="asgi_pass_through"),
        ],
    )
    def test_app(self, app, module: str | None, is_asgi: bool, expected_str: str | None) -> None:
        target = MagicMock() if is_asgi else app

        ctx = _AppContext(app=target, path=Path("/tmp"), module=module)  # ty: ignore[invalid-argument-type]

        if is_asgi:
            assert ctx.app is target
        else:
            assert ctx.app == expected_str

    def test_dir(self) -> None:
        ctx = _AppContext(app="app", path=Path("/tmp/abc"))

        assert ctx.dir == "/tmp/abc"


class TestCaseModel:
    def test_init(self) -> None:
        m = Model(url="/u", path="m.flm", name="my-model")

        assert m.url == "/u"
        assert m.path == "m.flm"
        assert m.name == "my-model"
        assert m.channel_scanner is None
        assert m.tool_scanner is None
        assert m.tool_parser is None
        assert m.params is None
        assert m.serving is None

    @pytest.mark.parametrize(
        ["channel_scanner", "tool_scanner", "tool_parser", "expected"],
        [
            pytest.param("auto", "auto", "auto", (None, None, None), id="auto_normalised_to_none"),
            pytest.param(
                "think", "tool_call", "json_object", ("think", "tool_call", "json_object"), id="refs_preserved"
            ),
            pytest.param(None, None, None, (None, None, None), id="defaults"),
        ],
    )
    def test_decoder_refs(
        self,
        channel_scanner: str | None,
        tool_scanner: str | None,
        tool_parser: str | None,
        expected: tuple[str | None, str | None, str | None],
    ) -> None:
        m = Model(
            url="/u",
            path="m.flm",
            name="n",
            channel_scanner=channel_scanner,
            tool_scanner=tool_scanner,
            tool_parser=tool_parser,
        )

        assert (m.channel_scanner, m.tool_scanner, m.tool_parser) == expected


class TestCaseModelSpec:
    @pytest.fixture(scope="function")
    def spec(self) -> _ModelSpec:
        return _ModelSpec()

    @pytest.mark.parametrize(
        ["value", "expected", "exception"],
        [
            pytest.param("m.flm", Model(url="/", path="m.flm", name="model"), None, id="bare_path"),
            pytest.param(
                "file=m.flm",
                Model(url="/", path="m.flm", name="model"),
                None,
                id="kv_only_file",
            ),
            pytest.param(
                "file=m.flm,url=/u,name=n",
                Model(url="/u", path="m.flm", name="n"),
                None,
                id="kv_full",
            ),
            pytest.param(
                "file=m.flm,channel_scanner=think",
                Model(url="/", path="m.flm", name="model", channel_scanner="think"),
                None,
                id="kv_channel_scanner",
            ),
            pytest.param(
                "file=m.flm,channel_scanner=passthrough",
                Model(url="/", path="m.flm", name="model", channel_scanner="passthrough"),
                None,
                id="kv_channel_scanner_passthrough",
            ),
            pytest.param(
                "file=m.flm,channel_scanner=auto",
                Model(url="/", path="m.flm", name="model"),
                None,
                id="kv_channel_scanner_auto",
            ),
            pytest.param(
                "file=m.flm,channel_scanner=off",
                None,
                (click.exceptions.BadParameter, "Unknown channel_scanner"),
                id="kv_channel_scanner_off_rejected",
            ),
            pytest.param(
                "file=m.flm,channel_scanner=mypkg.mod:custom",
                Model(url="/", path="m.flm", name="model", channel_scanner="mypkg.mod:custom"),
                None,
                id="kv_channel_scanner_import_path",
            ),
            pytest.param(
                "file=m.flm,tool_scanner=tool_call",
                Model(url="/", path="m.flm", name="model", tool_scanner="tool_call"),
                None,
                id="kv_tool_scanner",
            ),
            pytest.param(
                "file=m.flm,tool_scanner=auto",
                Model(url="/", path="m.flm", name="model"),
                None,
                id="kv_tool_scanner_auto",
            ),
            pytest.param(
                "file=m.flm,tool_scanner=passthrough",
                Model(url="/", path="m.flm", name="model", tool_scanner="passthrough"),
                None,
                id="kv_tool_scanner_passthrough",
            ),
            pytest.param(
                "file=m.flm,tool_scanner=off",
                None,
                (click.exceptions.BadParameter, "Unknown tool_scanner"),
                id="kv_tool_scanner_off_rejected",
            ),
            pytest.param(
                "file=m.flm,tool_parser=json_object",
                Model(url="/", path="m.flm", name="model", tool_parser="json_object"),
                None,
                id="kv_tool_parser",
            ),
            pytest.param(
                "file=m.flm,tool_parser=auto",
                Model(url="/", path="m.flm", name="model"),
                None,
                id="kv_tool_parser_auto",
            ),
            pytest.param(
                "file=m.flm,tool_parser=passthrough",
                Model(url="/", path="m.flm", name="model", tool_parser="passthrough"),
                None,
                id="kv_tool_parser_passthrough",
            ),
            pytest.param(
                "file=m.flm,tool_parser=off",
                None,
                (click.exceptions.BadParameter, "Unknown tool_parser"),
                id="kv_tool_parser_off_rejected",
            ),
            pytest.param(
                "file=m.flm,tool_parser=mypkg.mod:Parser",
                Model(url="/", path="m.flm", name="model", tool_parser="mypkg.mod:Parser"),
                None,
                id="kv_tool_parser_import_path",
            ),
            pytest.param(
                "file=m.flm,serving=native",
                Model(url="/", path="m.flm", name="model", serving=("native",)),
                None,
                id="kv_serving_single",
            ),
            pytest.param(
                "file=m.flm,serving=openai",
                Model(url="/", path="m.flm", name="model", serving=("openai",)),
                None,
                id="kv_serving_openai",
            ),
            pytest.param(
                "file=m.flm,serving=native:openai",
                Model(url="/", path="m.flm", name="model", serving=("native", "openai")),
                None,
                id="kv_serving_native_and_openai",
            ),
            pytest.param(
                "file=m.flm,params=temperature=0.7",
                Model(url="/", path="m.flm", name="model", params={"temperature": 0.7}),
                None,
                id="kv_params_single",
            ),
            pytest.param(
                "file=m.flm,params=temperature=0.7:max_tokens=200",
                Model(url="/", path="m.flm", name="model", params={"temperature": 0.7, "max_tokens": 200}),
                None,
                id="kv_params_multiple",
            ),
            pytest.param(
                "file=m.flm,params=reasoning=false:temperature=0.7",
                Model(url="/", path="m.flm", name="model", params={"reasoning": False, "temperature": 0.7}),
                None,
                id="kv_params_reasoning",
            ),
            pytest.param(
                "file=m.flm,params=name=hello",
                Model(url="/", path="m.flm", name="model", params={"name": "hello"}),
                None,
                id="kv_params_string_fallback",
            ),
            pytest.param(
                "file=m.flm,params=",
                None,
                (click.exceptions.BadParameter, "at least one"),
                id="empty_params_rejected",
            ),
            pytest.param(
                "file=m.flm,params=bogus",
                None,
                (click.exceptions.BadParameter, "key=value"),
                id="malformed_params_rejected",
            ),
            pytest.param(
                "url=/u,name=n", None, (click.exceptions.BadParameter, "'file' is required"), id="missing_file"
            ),
            pytest.param("file=m.flm,bogus=x", None, (click.exceptions.BadParameter, "Unknown key"), id="unknown_key"),
            pytest.param(
                "file=m.flm,lib=zzz",
                None,
                (click.exceptions.BadParameter, "Unknown key"),
                id="lib_no_longer_supported",
            ),
            pytest.param(
                "file=m.flm,channel_scanner=zzz",
                None,
                (click.exceptions.BadParameter, "Unknown channel_scanner"),
                id="unknown_channel_scanner",
            ),
            pytest.param(
                "file=m.flm,tool_scanner=zzz",
                None,
                (click.exceptions.BadParameter, "Unknown tool_scanner"),
                id="unknown_tool_scanner",
            ),
            pytest.param(
                "file=m.flm,tool_parser=zzz",
                None,
                (click.exceptions.BadParameter, "Unknown tool_parser"),
                id="unknown_tool_parser",
            ),
            pytest.param(
                "file=m.flm,serving=bogus",
                None,
                (click.exceptions.BadParameter, "Unknown serving"),
                id="unknown_serving",
            ),
            pytest.param(
                "file=m.flm,serving=",
                None,
                (click.exceptions.BadParameter, "at least one"),
                id="empty_serving",
            ),
            pytest.param("file=m.flm,bad", None, (click.exceptions.BadParameter, "key=value"), id="malformed_pair"),
        ],
        indirect=["exception"],
    )
    def test_convert(self, spec: _ModelSpec, value: str, expected: Model | None, exception) -> None:
        with exception:
            assert spec.convert(value, None, None) == expected

    @pytest.mark.parametrize(
        ["filename", "body", "expected", "exception"],
        [
            pytest.param(
                "spec.json",
                json.dumps(
                    {
                        "file": "m.flm",
                        "url": "/u",
                        "name": "n",
                        "channel_scanner": "auto",
                        "tool_scanner": "auto",
                        "tool_parser": "auto",
                        "params": {"temperature": 0.7, "max_tokens": 200},
                        "serving": ["native", "openai"],
                    }
                ),
                Model(
                    url="/u",
                    path="m.flm",
                    name="n",
                    params={"temperature": 0.7, "max_tokens": 200},
                    serving=("native", "openai"),
                ),
                None,
                id="full_spec",
            ),
            pytest.param(
                "spec.json",
                json.dumps({"file": "m.flm"}),
                Model(url="/", path="m.flm", name="model"),
                None,
                id="minimal_spec",
            ),
            pytest.param(
                "spec.json",
                json.dumps({"url": "/u"}),
                None,
                (click.exceptions.BadParameter, "'file' is required"),
                id="missing_file",
            ),
            pytest.param(
                "spec.json",
                json.dumps({"file": "m.flm", "bogus": "x"}),
                None,
                (click.exceptions.BadParameter, "Unknown key"),
                id="unknown_key",
            ),
            pytest.param(
                "spec.json",
                json.dumps({"file": "m.flm", "lib": "zzz"}),
                None,
                (click.exceptions.BadParameter, "Unknown key"),
                id="lib_no_longer_supported",
            ),
            pytest.param(
                "spec.json",
                json.dumps({"file": "m.flm", "serving": ["bogus"]}),
                None,
                (click.exceptions.BadParameter, "Unknown serving"),
                id="unknown_serving",
            ),
            pytest.param(
                "spec.json",
                json.dumps([{"file": "m.flm"}]),
                None,
                (click.exceptions.BadParameter, "must decode to a mapping"),
                id="not_a_mapping",
            ),
            pytest.param(
                "spec.txt",
                "file=m.flm",
                None,
                (click.exceptions.BadParameter, "Unsupported spec file extension"),
                id="unknown_extension",
            ),
            pytest.param(
                None,
                None,
                None,
                (click.exceptions.BadParameter, "Spec file not found"),
                id="not_found",
            ),
        ],
        indirect=["exception"],
    )
    def test_convert_file(
        self,
        spec: _ModelSpec,
        tmp_path: Path,
        filename: str | None,
        body: str | None,
        expected: Model | None,
        exception,
    ) -> None:
        if filename is None:
            spec_path = tmp_path / "missing.json"
        else:
            spec_path = tmp_path / filename
            assert body is not None
            spec_path.write_text(body)

        with exception:
            result = spec.convert(f"@{spec_path}", None, None)
            if expected is not None:
                assert result == expected


class TestCaseParseParams:
    @pytest.mark.parametrize(
        ["items", "expected", "exception"],
        [
            pytest.param([], {}, None, id="empty"),
            pytest.param(["a=1"], {"a": 1}, None, id="json_int"),
            pytest.param(["a=true"], {"a": True}, None, id="json_bool"),
            pytest.param(["name=hello"], {"name": "hello"}, None, id="string_fallback"),
            pytest.param(['payload={"a": 1}'], {"payload": {"a": 1}}, None, id="nested_json"),
            pytest.param(["a=1", "b=2"], {"a": 1, "b": 2}, None, id="multiple"),
            pytest.param(["bad-format"], None, (ValueError, "key=value"), id="missing_equals"),
        ],
        indirect=["exception"],
    )
    def test_parse_params(self, items: list[str], expected: dict | None, exception) -> None:
        with exception:
            assert _parse_params(items) == expected


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

    @pytest.mark.parametrize(
        ["model", "imports_decoder"],
        [
            pytest.param(Model(url="/", path="m.flm", name="ml"), False, id="ml_model_omits_decoder"),
            pytest.param(
                Model(url="/", path="m.flm", name="llm", channel_scanner="think"),
                True,
                id="decoder_model_imports_decoder",
            ),
        ],
    )
    def test_context_decoder_import(self, model: Model, imports_decoder: bool) -> None:
        with DictApp(models=[model]).context as ctx:
            module = str(ctx.app).split(":")[0]
            source = (Path(ctx.dir) / f"{module}.py").read_text()

        assert ("from flama.models.engine.llm.decoder import Decoder" in source) is imports_decoder
        compile(source, "<generated>", "exec")


class TestCaseStrApp:
    def test_context(self) -> None:
        s = StrApp("module.path:app_var")

        with s.context as ctx:
            assert ctx.app == "module.path:app_var"


class TestCaseOptions:
    @pytest.fixture(scope="function")
    def cmd(self) -> click.Command:
        @click.command()
        @options
        def cmd(app: DictApp) -> None:
            click.echo(f"title={app.title}")
            click.echo(f"count={len(app.models)}")
            for m in app.models:
                click.echo(f"{m.path}|{m.url}|{m.name}|{m.channel_scanner}|{m.tool_scanner}|{m.tool_parser}")

        return cmd

    @pytest.mark.parametrize(
        ["args", "expected_exit", "expected_lines"],
        [
            pytest.param(
                ["--model", "m.flm"],
                0,
                ["count=1", "m.flm|/|model|None|None|None"],
                id="bare_path_defaults",
            ),
            pytest.param(
                ["--model", "file=m.flm,url=/m/,name=m"],
                0,
                ["count=1", "m.flm|/m/|m|None|None|None"],
                id="kv_url_and_name",
            ),
            pytest.param(
                ["--model", "file=m.flm,channel_scanner=think"],
                0,
                ["count=1", "m.flm|/|model|think|None|None"],
                id="kv_channel_scanner",
            ),
            pytest.param(
                ["--model", "file=m.flm,tool_scanner=tool_call"],
                0,
                ["count=1", "m.flm|/|model|None|tool_call|None"],
                id="kv_tool_scanner",
            ),
            pytest.param(
                ["--model", "file=m.flm,tool_parser=json_object"],
                0,
                ["count=1", "m.flm|/|model|None|None|json_object"],
                id="kv_tool_parser",
            ),
            pytest.param(
                ["--model", "file=m1.flm,url=/m1/,name=m1", "--model", "m2.flm"],
                0,
                ["count=2", "m1.flm|/m1/|m1|None|None|None", "m2.flm|/|model|None|None|None"],
                id="multiple_mixed_forms",
            ),
            pytest.param(["--model", "file=m.flm,lib=vllm"], 2, [], id="lib_rejected"),
            pytest.param(["--model", "file=m.flm,channel_scanner=bogus"], 2, [], id="invalid_channel_scanner_rejected"),
            pytest.param(["--model", "file=m.flm,tool_scanner=bogus"], 2, [], id="invalid_tool_scanner_rejected"),
            pytest.param(["--model", "file=m.flm,tool_parser=bogus"], 2, [], id="invalid_tool_parser_rejected"),
            pytest.param(["--model", "file=m.flm,bogus=x"], 2, [], id="unknown_key_rejected"),
            pytest.param(["--model", "url=/m/,name=m"], 2, [], id="missing_file_rejected"),
            pytest.param(["--model", "file=m.flm,bad"], 2, [], id="malformed_pair_rejected"),
        ],
    )
    def test_options(
        self,
        runner: CliRunner,
        cmd: click.Command,
        args: list[str],
        expected_exit: int,
        expected_lines: list[str],
    ) -> None:
        result = runner.invoke(cmd, args)

        assert result.exit_code == expected_exit, result.output
        for line in expected_lines:
            assert line in result.output

    def test_options_passes_app_title(self, runner: CliRunner, cmd: click.Command) -> None:
        result = runner.invoke(cmd, ["--model", "m.flm", "--app-title", "MyApp"])

        assert result.exit_code == 0, result.output
        assert "title=MyApp" in result.output
