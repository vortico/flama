import pathlib
import warnings
from unittest.mock import MagicMock, call, mock_open, patch

import jinja2
import pytest

from flama import exceptions, http
from flama.http.templates import HTMLFileResponse, HTMLTemplateResponse, HTMLTemplatesEnvironment, _FlamaLoader


class TestCaseHTMLFileResponse:
    def test_init(self):
        content = "<html></html>"
        with patch("builtins.open", mock_open(read_data=content)):
            response = HTMLFileResponse("foo.html")

        assert response.body == content.encode()

    def test_init_error(self):
        error_detail = "Foo error"
        with (
            patch("builtins.open", side_effect=ValueError(error_detail)),
            pytest.raises(exceptions.HTTPException) as exc,
        ):
            HTMLFileResponse("foo.html")

            assert exc.status_code == 500
            assert exc.detail == error_detail


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
        ["context"], (pytest.param({"foo": "bar"}, id="context"), pytest.param(None, id="no_context"))
    )
    def test_init(self, context):
        template_mock = MagicMock()
        template_mock.render.return_value = "foo"
        environment_mock = MagicMock(spec=jinja2.Environment)
        environment_mock.get_template.return_value = template_mock
        with (
            patch.object(HTMLTemplateResponse, "templates", new=environment_mock),
            patch.object(http.HTMLResponse, "__init__", return_value=None) as super_mock,
        ):
            HTMLTemplateResponse("foo.html", context)

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
