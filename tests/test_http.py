import dataclasses
import datetime
import enum
import json
import pathlib
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock, call, mock_open, patch

import jinja2
import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields

from flama import exceptions, http, types


@dataclasses.dataclass
class Foo:
    bar: int


class TestCaseRequest:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/request/")
        async def get_request(request: http.Request):
            return {
                "method": str(request.method),
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": (await request.body()).decode("utf-8"),
            }

    async def test_request(self, client):
        expected_response = {
            "method": "GET",
            "url": "http://localapp/request/",
            "headers": {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate",
                "connection": "keep-alive",
                "host": "localapp",
            },
            "body": "",
        }

        response = await client.get("/request/")
        response_json = response.json()
        del response_json["headers"]["user-agent"]

        assert response_json == expected_response, str(response_json)


class TestCaseResponse:
    async def test_call(self):
        response = http.Response()
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.Response.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]

    def test_eq(self):
        assert http.Response(content="foo") == http.Response(content="foo")
        assert http.Response(content="foo") != http.Response(content="bar")


class TestCaseHTMLResponse:
    async def test_call(self):
        response = http.HTMLResponse()
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.HTMLResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCasePlainTextResponse:
    async def test_call(self):
        response = http.PlainTextResponse()
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.PlainTextResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCaseJSONResponse:
    @pytest.fixture
    def schema(self):
        return Mock()

    async def test_call(self):
        response = http.JSONResponse(content={})
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.JSONResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]

    @pytest.mark.parametrize(
        ["content", "result", "exception"],
        (
            pytest.param(
                {"foo": {"bar": [1, "foobar", 2.0, True, None]}},
                {"foo": {"bar": [1, "foobar", 2.0, True, None]}},
                None,
                id="default",
            ),
            pytest.param({"foo": pathlib.Path("foo/bar.json")}, {"foo": "foo/bar.json"}, None, id="path"),
            pytest.param({"foo": b"bar"}, {"foo": "bar"}, None, id="bytes"),
            pytest.param({"foo": bytearray([1, 2, 3])}, {"foo": "\x01\x02\x03"}, None, id="bytearray"),
            pytest.param({"foo": enum.Enum("Foo", ["bar"]).bar}, {"foo": 1}, None, id="enum"),
            pytest.param({"foo": uuid.UUID(int=0)}, {"foo": "00000000-0000-0000-0000-000000000000"}, None, id="uuid"),
            pytest.param({"foo": {"bar"}}, {"foo": ["bar"]}, None, id="set"),
            pytest.param({"foo": frozenset({"bar"})}, {"foo": ["bar"]}, None, id="set"),
            pytest.param(
                {"foo": datetime.datetime(2023, 9, 20, 11, 30, 0)}, {"foo": "2023-09-20T11:30:00"}, None, id="datetime"
            ),
            pytest.param({"foo": datetime.date(2023, 9, 20)}, {"foo": "2023-09-20"}, None, id="date"),
            pytest.param({"foo": datetime.time(11, 30, 0)}, {"foo": "11:30:00"}, None, id="time"),
            pytest.param(
                {"foo": datetime.timedelta(days=1, hours=20, minutes=30, seconds=10, milliseconds=10, microseconds=6)},
                {"foo": "P1D20H30M10.010006S"},
                None,
                id="timedelta",
            ),
            pytest.param({"foo": Exception}, {"foo": "Exception"}, None, id="exception_class"),
            pytest.param({"foo": Exception("bar")}, {"foo": "Exception('bar')"}, None, id="exception_obj"),
            pytest.param({"foo": "bar"}, {"foo": "bar"}, None, id="schema"),
            pytest.param({"foo": Foo(bar=1)}, {"foo": {"bar": 1}}, None, id="dataclass"),
            pytest.param({"foo": Mock()}, None, TypeError, id="error"),
        ),
        indirect=["exception"],
    )
    def test_render(self, content, result, exception):
        with exception:
            response = http.JSONResponse(content=content)

            assert json.loads(response.body.decode()) == result


class TestCaseRedirectResponse:
    async def test_call(self):
        response = http.RedirectResponse(url="")
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.RedirectResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCaseStreamingResponse:
    async def test_call(self):
        response = http.StreamingResponse(content=(x for x in "foo"))
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.StreamingResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCaseFileResponse:
    async def test_call(self):
        response = http.FileResponse(path="")
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.FileResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCaseAPIResponse:
    @pytest.fixture(scope="function")
    def schema(self, app):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model("Puppy", name=(str, ...))
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(title="Puppy", fields={"name": typesystem.fields.String()})
        elif app.schema.schema_library.lib == marshmallow:
            schema = type("Puppy", (marshmallow.Schema,), {"name": marshmallow.fields.String(required=True)})
        else:
            raise ValueError("Wrong schema lib")

        return schema

    def test_init(self, schema):
        with patch("flama.http.starlette.responses.JSONResponse.__init__"):
            response = http.APIResponse(schema=schema)

        assert response.schema == schema

    @pytest.mark.parametrize(
        ["use_schema", "content", "expected", "exception"],
        (
            pytest.param(True, {"name": "Canna"}, '{"name":"Canna"}', None, id="schema_and_content"),
            pytest.param(False, {}, "", None, id="no_content"),
            pytest.param(False, {"name": "Canna"}, '{"name":"Canna"}', None, id="no_schema"),
            pytest.param(True, {"foo": "bar"}, "", exceptions.SerializationError, id="error"),
        ),
        indirect=["exception"],
    )
    def test_render(self, schema, use_schema, content, expected, exception):
        with exception:
            response = http.APIResponse(schema=schema if use_schema else None, content=content)
            assert response.body.decode() == expected


class TestCaseAPIErrorResponse:
    def test_init(self):
        detail = "foo"
        exception = ValueError()
        status_code = 401
        expected_result = {"detail": "foo", "error": "ValueError", "status_code": 401}

        response = http.APIErrorResponse(detail=detail, status_code=status_code, exception=exception)

        assert response.detail == detail
        assert response.exception == exception
        assert response.status_code == status_code
        assert json.loads(response.body.decode()) == expected_result


class TestCaseHTMLFileResponse:
    def test_init(self):
        content = "<html></html>"
        with patch("builtins.open", mock_open(read_data=content)):
            response = http.HTMLFileResponse("foo.html")

        assert response.body == content.encode()

    def test_init_error(self):
        error_detail = "Foo error"
        with (
            patch("builtins.open", side_effect=ValueError(error_detail)),
            pytest.raises(exceptions.HTTPException) as exc,
        ):
            http.HTMLFileResponse("foo.html")

            assert exc.status_code == 500
            assert exc.detail == error_detail


class TestCaseHTMLTemplatesEnvironment:
    @pytest.fixture
    def environment(self):
        return http.HTMLTemplatesEnvironment()

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
            patch.object(http.HTMLTemplateResponse, "templates", new=environment_mock),
            patch.object(http.HTMLResponse, "__init__", return_value=None) as super_mock,
        ):
            http.HTMLTemplateResponse("foo.html", context)

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
        ):
            http._FlamaLoader()

            if mkdir_call:
                assert mkdir_mock.call_args_list == [call(exist_ok=True)]


class TestCaseOpenAPIResponse:
    @pytest.mark.parametrize(
        "test_input,expected,exception",
        (
            pytest.param({"foo": "bar"}, {"foo": "bar"}, None, id="success"),
            pytest.param("foo", None, ValueError("The schema must be a dictionary"), id="wrong_content"),
        ),
        indirect=("exception",),
    )
    def test_render(self, test_input, expected, exception):
        with exception:
            response = http.OpenAPIResponse(test_input)

            assert json.loads(response.body.decode()) == expected

    async def test_call(self):
        response = http.OpenAPIResponse(content={})
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.schemas.OpenAPIResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]
