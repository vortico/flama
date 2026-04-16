import pathlib
import warnings
from unittest.mock import MagicMock, call, mock_open, patch

import jinja2
import pytest

from flama import exceptions
from flama.http.responses.html import HTMLResponse
from flama.http.responses.templates import (
    HTMLTemplateResponse,
    HTMLTemplatesEnvironment,
    _FlamaLoader,
)


class TestCaseHTMLFileResponse:
    @pytest.mark.parametrize(
        ["side_effect", "expected_body", "exception"],
        [
            pytest.param(None, b"<html></html>", None, id="success"),
            pytest.param(ValueError("Foo error"), None, exceptions.HTTPException, id="error"),
        ],
        indirect=["exception"],
    )
    def test_init(self, side_effect, expected_body, exception):
        open_fn = mock_open(read_data="<html></html>") if side_effect is None else MagicMock(side_effect=side_effect)

        with exception, patch("builtins.open", open_fn):
            response = HTMLResponse(path="foo.html")

            assert response.body == expected_body


class TestCaseHTMLTemplatesEnvironment:
    @pytest.fixture
    def environment(self):
        return HTMLTemplatesEnvironment()

    @pytest.mark.parametrize(
        ["value", "result"],
        (
            pytest.param("& < > \" ' \n", "&amp; &lt; &gt; &quot; &#x27; &#10;&#13;", id="str"),
            pytest.param(1, 1, id="int"),
            pytest.param(1.0, 1.0, id="float"),
            pytest.param(True, True, id="bool"),
            pytest.param(None, None, id="none"),
            pytest.param(
                ["foo", 1, 1.0, True, None, ["nested", "&"], ("nested", "&"), {"nested": "&"}],
                ["foo", 1, 1.0, True, None, ["nested", "&amp;"], ["nested", "&amp;"], {"nested": "&amp;"}],
                id="list",
            ),
            pytest.param(
                ("foo", 1, 1.0, True, None, ["nested", "&"], ("nested", "&"), {"nested": "&"}),
                ["foo", 1, 1.0, True, None, ["nested", "&amp;"], ["nested", "&amp;"], {"nested": "&amp;"}],
                id="tuple",
            ),
            pytest.param(
                {
                    "str": "foo",
                    "int": 1,
                    "float": 1.0,
                    "bool": True,
                    "null": None,
                    "list": ["nested", "&"],
                    "tuple": ("nested", "&"),
                    "dict": {"nested": "&"},
                },
                {
                    "str": "foo",
                    "int": 1,
                    "float": 1.0,
                    "bool": True,
                    "null": None,
                    "list": ["nested", "&amp;"],
                    "tuple": ["nested", "&amp;"],
                    "dict": {"nested": "&amp;"},
                },
                id="dict",
            ),
        ),
    )
    def test_escape(self, environment, value, result):
        assert environment._escape(value) == result

    @pytest.mark.parametrize(
        ["value", "result"],
        (
            pytest.param("& < > \" ' \n", "&amp; &lt; &gt; &quot; &#x27; &#10;&#13;", id="str"),
            pytest.param("1", "1", id="int"),
            pytest.param("1.0", "1.0", id="float"),
            pytest.param("true", "true", id="bool"),
            pytest.param("null", "null", id="none"),
        ),
    )
    def test_safe(self, environment, value, result):
        assert environment.safe(value) == result

    @pytest.mark.parametrize(
        ["value", "result"],
        (
            pytest.param("& < > \" ' \n", '\\"&amp; &lt; &gt; &quot; &#x27; &#10;&#13;\\"', id="str"),
            pytest.param(1, "1", id="int"),
            pytest.param(1.0, "1.0", id="float"),
            pytest.param(True, "true", id="bool"),
            pytest.param(None, "null", id="none"),
            pytest.param(
                ["foo", 1, 1.0, True, None, ["nested", "&"], ("nested", "&"), {"nested": "&"}],
                '[\\"foo\\", 1, 1.0, true, null, [\\"nested\\", \\"&amp;\\"], [\\"nested\\", \\"&amp;\\"], '
                '{\\"nested\\": \\"&amp;\\"}]',
                id="list",
            ),
            pytest.param(
                ("foo", 1, 1.0, True, None, ["nested", "&"], ("nested", "&"), {"nested": "&"}),
                '[\\"foo\\", 1, 1.0, true, null, [\\"nested\\", \\"&amp;\\"], [\\"nested\\", \\"&amp;\\"], '
                '{\\"nested\\": \\"&amp;\\"}]',
                id="tuple",
            ),
            pytest.param(
                {
                    "str": "foo",
                    "int": 1,
                    "float": 1.0,
                    "bool": True,
                    "null": None,
                    "list": ["nested", "&"],
                    "tuple": ("nested", "&"),
                    "dict": {"nested": "&"},
                },
                '{\\"str\\": \\"foo\\", \\"int\\": 1, \\"float\\": 1.0, \\"bool\\": true, \\"null\\": null, '
                '\\"list\\": [\\"nested\\", \\"&amp;\\"], \\"tuple\\": [\\"nested\\", \\"&amp;\\"], '
                '\\"dict\\": {\\"nested\\": \\"&amp;\\"}}',
                id="dict",
            ),
        ),
    )
    def test_safe_json(self, environment, value, result):
        assert environment.safe_json(value) == result


class TestCaseHTMLTemplateResponse:
    @pytest.mark.parametrize(
        ["context", "render_side_effect", "exception"],
        [
            pytest.param({"foo": "bar"}, None, None, id="context"),
            pytest.param(None, None, None, id="no_context"),
            pytest.param(None, jinja2.TemplateNotFound("missing.html"), exceptions.HTTPException, id="render_error"),
        ],
        indirect=["exception"],
    )
    def test_init(self, context, render_side_effect, exception):
        template_mock = MagicMock()
        if render_side_effect is not None:
            template_mock.render.side_effect = render_side_effect
        else:
            template_mock.render.return_value = "foo"
        environment_mock = MagicMock(spec=jinja2.Environment)
        environment_mock.get_template.return_value = template_mock
        with (
            exception,
            patch.object(HTMLTemplateResponse, "templates", new=environment_mock),
            patch.object(HTMLResponse, "__init__", return_value=None) as super_mock,
        ):
            HTMLTemplateResponse("foo.html", context=context)

            assert super_mock.call_args_list == [call("foo")]


class TestCaseFlamaLoader:
    @pytest.mark.parametrize(
        ["import_mock", "path_exists_mock", "mkdir_call", "exception"],
        [
            pytest.param(
                MagicMock(find_spec=MagicMock()),
                True,
                False,
                None,
                id="ok",
            ),
            pytest.param(
                MagicMock(find_spec=MagicMock()),
                False,
                True,
                None,
                id="ok_create_templates_path",
            ),
            pytest.param(
                MagicMock(find_spec=MagicMock(return_value=None)),
                True,
                False,
                exceptions.ApplicationError("Flama package not found"),
                id="error_flama_package_not_found",
            ),
        ],
        indirect=["exception"],
    )
    def test_init(self, import_mock, path_exists_mock, mkdir_call, exception):
        with (
            exception,
            patch("jinja2.PackageLoader.__init__"),
            patch("importlib.util", import_mock),
            patch.object(pathlib.Path, "exists", return_value=path_exists_mock),
            patch.object(pathlib.Path, "mkdir") as mkdir_mock,
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore")
            _FlamaLoader()

            if mkdir_call:
                assert mkdir_mock.call_args_list == [call(exist_ok=True)]
