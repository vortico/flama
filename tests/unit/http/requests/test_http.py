from unittest.mock import patch

import pytest

from flama import http, types
from flama.http.data_structures import FormData, UploadFile
from flama.http.requests.http import Request, _parse_content_type


class TestCaseParseContentType:
    @pytest.mark.parametrize(
        ["header", "expected_type", "expected_params"],
        [
            pytest.param(
                "multipart/form-data; boundary=----TestBoundary",
                "multipart/form-data",
                {"boundary": "----TestBoundary"},
                id="multipart",
            ),
            pytest.param("application/json", "application/json", {}, id="no_params"),
            pytest.param("text/html; charset=utf-8", "text/html", {"charset": "utf-8"}, id="charset"),
            pytest.param(
                'multipart/form-data; boundary="quoted"',
                "multipart/form-data",
                {"boundary": "quoted"},
                id="quoted_param",
            ),
            pytest.param("TEXT/HTML", "text/html", {}, id="case_insensitive"),
            pytest.param("", "", {}, id="empty"),
            pytest.param(
                "text/plain; charset=utf-8; boundary=abc",
                "text/plain",
                {"charset": "utf-8", "boundary": "abc"},
                id="multiple_params",
            ),
            pytest.param(
                "text/plain; noequals; charset=utf-8",
                "text/plain",
                {"charset": "utf-8"},
                id="param_without_equals",
            ),
        ],
    )
    def test_parse(self, header, expected_type, expected_params):
        media_type, params = _parse_content_type(header)

        assert media_type == expected_type
        assert params == expected_params


class TestCaseRequest:
    @pytest.fixture
    def scope(self):
        return types.Scope(
            {
                "type": "http",
                "method": "POST",
                "path": "/submit",
                "query_string": b"",
                "headers": [
                    (b"host", b"localhost"),
                    (b"content-type", b"application/json"),
                ],
                "server": ("localhost", 8000),
                "scheme": "http",
                "root_path": "",
            }
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/")
        async def get_request(request: http.Request):
            return {
                "method": str(request.method),
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": (await request.body()).decode("utf-8"),
            }

    @staticmethod
    def _make_receive(body: bytes, *, chunked: bool = False) -> types.Receive:
        chunks: list[types.Message]
        if chunked and body:
            mid = len(body) // 2
            chunks = [
                types.Message({"type": "http.request", "body": body[:mid], "more_body": True}),
                types.Message({"type": "http.request", "body": body[mid:], "more_body": False}),
            ]
        else:
            chunks = [types.Message({"type": "http.request", "body": body, "more_body": False})]
        it = iter(chunks)

        async def receive() -> types.Message:
            return next(it)

        return receive  # type: ignore[return-value]

    @pytest.mark.parametrize(
        ["scope", "exception"],
        (
            pytest.param(
                types.Scope(
                    {
                        "type": "http",
                        "method": "POST",
                        "path": "/submit",
                        "query_string": b"",
                        "headers": [
                            (b"host", b"localhost"),
                            (b"content-type", b"application/json"),
                        ],
                        "server": ("localhost", 8000),
                        "scheme": "http",
                        "root_path": "",
                    }
                ),
                None,
                id="ok",
            ),
            pytest.param(
                types.Scope({"type": "websocket", "path": "/", "headers": []}),
                RuntimeError("Request scope type must be 'http'"),
                id="invalid_scope",
            ),
        ),
        indirect=["exception"],
    )
    def test_init(self, scope, exception):
        with exception:
            request = Request(scope)

            assert request.method == scope["method"]

    def test_method(self, scope):
        request = Request(scope)

        assert request.method == "POST"

    @pytest.mark.parametrize(
        ["has_receive", "exception"],
        [
            pytest.param(True, None, id="set"),
            pytest.param(False, RuntimeError("Receive channel"), id="empty"),
        ],
        indirect=["exception"],
    )
    async def test_receive(self, scope, has_receive, exception):
        if has_receive:
            receive = self._make_receive(b"")
            request = Request(scope, receive)

            assert request.receive is receive
        else:
            request = Request(types.Scope({"type": "http", "method": "GET", "path": "/", "headers": []}))

            with exception:
                await request.body()

    @pytest.mark.parametrize(
        ["body_bytes", "chunked", "check_cached"],
        [
            pytest.param(b'{"key": "value"}', False, False, id="simple"),
            pytest.param(b"data", False, True, id="cached"),
            pytest.param(b"abcdefgh", True, False, id="chunked"),
        ],
    )
    async def test_body(self, scope, body_bytes, chunked, check_cached):
        request = Request(scope, self._make_receive(body_bytes, chunked=chunked))

        body = await request.body()

        assert body == body_bytes
        if check_cached:
            assert await request.body() is body

    @pytest.mark.parametrize(
        ["body_bytes", "expected", "check_cached"],
        [
            pytest.param(b'{"key": "value"}', {"key": "value"}, False, id="simple"),
            pytest.param(b'{"x": 1}', {"x": 1}, True, id="cached"),
        ],
    )
    async def test_json(self, scope, body_bytes, expected, check_cached):
        request = Request(scope, self._make_receive(body_bytes))

        data = await request.json()

        assert data == expected
        if check_cached:
            assert await request.json() is data

    @pytest.mark.parametrize(
        ["scenario"],
        [
            pytest.param("normal", id="normal"),
            pytest.param("consumed", id="consumed"),
            pytest.param("after_body", id="after_body"),
            pytest.param("disconnect", id="disconnect"),
            pytest.param("unknown_message", id="unknown_message"),
        ],
    )
    async def test_stream(self, scope, scenario):  # noqa
        if scenario == "normal":
            request = Request(scope, self._make_receive(b"abcdef", chunked=True))

            chunks = [chunk async for chunk in request.stream()]

            assert b"".join(chunks) == b"abcdef"

        elif scenario == "consumed":
            request = Request(scope, self._make_receive(b"data"))
            async for _ in request.stream():
                pass

            with pytest.raises(RuntimeError, match="Stream consumed"):
                async for _ in request.stream():
                    pass

        elif scenario == "after_body":
            request = Request(scope, self._make_receive(b"data"))
            await request.body()

            chunks = [chunk async for chunk in request.stream()]

            assert b"".join(chunks) == b"data"

        elif scenario == "disconnect":

            async def receive():
                return types.Message({"type": "http.disconnect"})

            request = Request(scope, receive)  # type: ignore[arg-type]

            with pytest.raises(ConnectionAbortedError):
                async for _ in request.stream():
                    pass

        elif scenario == "unknown_message":
            messages = iter(
                [
                    types.Message({"type": "http.unknown"}),
                    types.Message({"type": "http.request", "body": b"ok", "more_body": False}),
                ]
            )

            async def receive():
                return next(messages)

            request = Request(scope, receive)  # type: ignore[arg-type]

            chunks = [chunk async for chunk in request.stream()]

            assert b"".join(chunks) == b"ok"

    @pytest.mark.parametrize(
        ["scenario", "expected"],
        [
            pytest.param("timeout", False, id="false"),
            pytest.param("disconnect_message", True, id="true_from_disconnect"),
            pytest.param("via_stream", True, id="true_via_stream"),
            pytest.param("already_flagged", True, id="already_flagged"),
        ],
    )
    async def test_is_disconnected(self, scope, scenario, expected):
        if scenario == "already_flagged":
            request = Request(scope, self._make_receive(b""))
            request._is_disconnected = True
        elif scenario == "timeout":

            async def receive():
                raise TimeoutError

            request = Request(scope, receive)  # type: ignore[arg-type]
        else:

            async def receive():
                return types.Message({"type": "http.disconnect"})

            request = Request(scope, receive)  # type: ignore[arg-type]

            if scenario == "via_stream":
                with pytest.raises(ConnectionAbortedError):
                    async for _ in request.stream():
                        pass

        if scenario == "disconnect_message":

            async def wait_for_immediate(awaitable, **kwargs):
                return await awaitable

            with patch("flama.http.requests.http.asyncio.wait_for", wait_for_immediate):
                result = await request.is_disconnected()
            assert request._is_disconnected is True
        else:
            result = await request.is_disconnected()

        assert result is expected

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [
            pytest.param("no_send", RuntimeError("Send channel"), id="no_send"),
            pytest.param("with_extension", None, id="with_extension"),
            pytest.param("no_extension", None, id="no_extension"),
        ],
        indirect=["exception"],
    )
    async def test_send_push_promise(self, scope, scenario, exception):
        messages: list[types.Message] = []

        async def send(message: types.Message) -> None:
            messages.append(message)

        if scenario == "no_send":
            s = types.Scope(
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/",
                    "headers": [],
                    "extensions": {"http.response.push": {}},
                }
            )
            request = Request(s)

            with exception:
                await request.send_push_promise("/push")
            return

        if scenario == "with_extension":
            scope["headers"] = [(b"accept", b"text/html"), (b"user-agent", b"TestAgent")]
            scope["extensions"] = {"http.response.push": {}}

        request = Request(scope, self._make_receive(b""), send)  # type: ignore[arg-type]
        await request.send_push_promise("/pushed")

        if scenario == "with_extension":
            assert len(messages) == 1
            assert messages[0]["type"] == "http.response.push"
            assert messages[0]["path"] == "/pushed"
        else:
            assert messages == []

    @pytest.mark.parametrize(
        ["content_type", "body", "scenario"],
        [
            pytest.param("application/x-www-form-urlencoded", b"name=alice&age=30", "urlencoded", id="urlencoded"),
            pytest.param(
                "multipart/form-data; boundary=----TestBoundary",
                b"------TestBoundary\r\n"
                b'Content-Disposition: form-data; name="field"\r\n\r\n'
                b"value\r\n"
                b"------TestBoundary\r\n"
                b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
                b"Content-Type: text/plain\r\n\r\n"
                b"file content\r\n"
                b"------TestBoundary--\r\n",
                "multipart",
                id="multipart",
            ),
            pytest.param("application/x-www-form-urlencoded", b"k=v", "cached", id="cached"),
            pytest.param("application/json", b"{}", "unknown_content_type", id="unknown_content_type"),
            pytest.param("application/x-www-form-urlencoded", b"k=v", "close", id="close"),
            pytest.param("application/x-www-form-urlencoded", b"", "close_without_form", id="close_without_form"),
        ],
    )
    async def test_form(self, content_type, body, scenario):
        scope = types.Scope(
            {
                "type": "http",
                "method": "POST",
                "path": "/form",
                "query_string": b"",
                "headers": [(b"content-type", content_type.encode())],
                "server": ("localhost", 8000),
                "scheme": "http",
                "root_path": "",
            }
        )

        async def receive() -> types.Message:
            return types.Message({"type": "http.request", "body": body, "more_body": False})

        request = Request(scope, receive)  # type: ignore[arg-type]

        if scenario == "close_without_form":
            await request.close()
            return

        form = await request.form()

        if scenario == "urlencoded":
            assert isinstance(form, FormData)
            assert dict(form) == {"name": "alice", "age": "30"}
        elif scenario == "multipart":
            assert form["field"] == "value"
            assert isinstance(form["file"], UploadFile)
            assert form["file"].filename == "test.txt"
            assert await form["file"].read() == b"file content"
        elif scenario == "cached":
            assert await request.form() is form
        elif scenario == "unknown_content_type":
            assert dict(form) == {}
        elif scenario == "close":
            await request.close()

    async def test_integration(self, client):
        expected_response = {
            "method": "GET",
            "url": "http://localapp/",
            "headers": {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate",
                "connection": "keep-alive",
                "host": "localapp",
            },
            "body": "",
        }

        response = await client.get("/")
        response_json = response.json()
        del response_json["headers"]["user-agent"]

        assert response_json == expected_response, str(response_json)
