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

    def test_receive(self, scope):
        receive = self._make_receive(b"")
        request = Request(scope, receive)

        assert request.receive is receive

    async def test_body(self, scope):
        request = Request(scope, self._make_receive(b'{"key": "value"}'))

        body = await request.body()

        assert body == b'{"key": "value"}'

    async def test_body_cached(self, scope):
        request = Request(scope, self._make_receive(b"data"))

        first = await request.body()
        second = await request.body()

        assert first is second

    async def test_body_chunked(self, scope):
        request = Request(scope, self._make_receive(b"abcdefgh", chunked=True))

        body = await request.body()

        assert body == b"abcdefgh"

    async def test_json(self, scope):
        request = Request(scope, self._make_receive(b'{"key": "value"}'))

        data = await request.json()

        assert data == {"key": "value"}

    async def test_json_cached(self, scope):
        request = Request(scope, self._make_receive(b'{"x": 1}'))

        first = await request.json()
        second = await request.json()

        assert first is second

    async def test_stream(self, scope):
        request = Request(scope, self._make_receive(b"abcdef", chunked=True))

        chunks = []
        async for chunk in request.stream():
            chunks.append(chunk)

        assert b"".join(chunks) == b"abcdef"

    async def test_stream_consumed(self, scope):
        request = Request(scope, self._make_receive(b"data"))
        async for _ in request.stream():
            pass

        with pytest.raises(RuntimeError, match="Stream consumed"):
            async for _ in request.stream():
                pass

    async def test_stream_after_body(self, scope):
        request = Request(scope, self._make_receive(b"data"))
        await request.body()

        chunks = []
        async for chunk in request.stream():
            chunks.append(chunk)

        assert b"".join(chunks) == b"data"

    async def test_stream_disconnect(self, scope):
        async def receive():
            return types.Message({"type": "http.disconnect"})

        request = Request(scope, receive)  # type: ignore[arg-type]

        with pytest.raises(ConnectionAbortedError):
            async for _ in request.stream():
                pass

    async def test_empty_receive(self):
        scope = types.Scope({"type": "http", "method": "GET", "path": "/", "headers": []})
        request = Request(scope)

        with pytest.raises(RuntimeError, match="Receive channel"):
            await request.body()

    async def test_empty_send(self):
        scope = types.Scope(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [],
                "extensions": {"http.response.push": {}},
            }
        )
        request = Request(scope)

        with pytest.raises(RuntimeError, match="Send channel"):
            await request.send_push_promise("/push")

    async def test_is_disconnected_false(self, scope):
        async def receive():
            raise TimeoutError

        request = Request(scope, receive)  # type: ignore[arg-type]

        assert await request.is_disconnected() is False

    async def test_is_disconnected_true_via_stream(self, scope):
        async def receive():
            return types.Message({"type": "http.disconnect"})

        request = Request(scope, receive)  # type: ignore[arg-type]

        with pytest.raises(ConnectionAbortedError):
            async for _ in request.stream():
                pass

        assert await request.is_disconnected() is True

    async def test_is_disconnected_already_flagged(self, scope):
        request = Request(scope, self._make_receive(b""))

        request._is_disconnected = True

        assert await request.is_disconnected() is True

    async def test_send_push_promise(self, scope):
        scope["headers"] = [
            (b"accept", b"text/html"),
            (b"user-agent", b"TestAgent"),
        ]
        scope["extensions"] = {"http.response.push": {}}
        messages: list[types.Message] = []

        async def send(message: types.Message) -> None:
            messages.append(message)

        request = Request(scope, self._make_receive(b""), send)  # type: ignore[arg-type]
        await request.send_push_promise("/pushed")

        assert len(messages) == 1
        assert messages[0]["type"] == "http.response.push"
        assert messages[0]["path"] == "/pushed"

    async def test_send_push_promise_no_extension(self, scope):
        messages: list[types.Message] = []

        async def send(message: types.Message) -> None:
            messages.append(message)

        request = Request(scope, self._make_receive(b""), send)  # type: ignore[arg-type]
        await request.send_push_promise("/pushed")

        assert messages == []


class TestCaseRequestForm:
    @staticmethod
    def _make_receive(body: bytes) -> types.Receive:
        async def receive() -> types.Message:
            return types.Message({"type": "http.request", "body": body, "more_body": False})

        return receive  # type: ignore[return-value]

    @pytest.fixture
    def urlencoded_scope(self):
        return types.Scope(
            {
                "type": "http",
                "method": "POST",
                "path": "/form",
                "query_string": b"",
                "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
                "server": ("localhost", 8000),
                "scheme": "http",
                "root_path": "",
            }
        )

    async def test_urlencoded(self, urlencoded_scope):
        request = Request(urlencoded_scope, self._make_receive(b"name=alice&age=30"))

        form = await request.form()

        assert isinstance(form, FormData)
        assert dict(form) == {"name": "alice", "age": "30"}

    async def test_multipart(self):
        body = (
            b"------TestBoundary\r\n"
            b'Content-Disposition: form-data; name="field"\r\n\r\n'
            b"value\r\n"
            b"------TestBoundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
            b"file content\r\n"
            b"------TestBoundary--\r\n"
        )
        scope = types.Scope(
            {
                "type": "http",
                "method": "POST",
                "path": "/upload",
                "query_string": b"",
                "headers": [(b"content-type", b"multipart/form-data; boundary=----TestBoundary")],
                "server": ("localhost", 8000),
                "scheme": "http",
                "root_path": "",
            }
        )

        request = Request(scope, self._make_receive(body))
        form = await request.form()

        assert form["field"] == "value"
        assert isinstance(form["file"], UploadFile)
        assert form["file"].filename == "test.txt"
        assert await form["file"].read() == b"file content"

    async def test_cached(self, urlencoded_scope):
        request = Request(urlencoded_scope, self._make_receive(b"k=v"))

        first = await request.form()
        second = await request.form()

        assert first is second

    async def test_unknown_content_type(self):
        scope = types.Scope(
            {
                "type": "http",
                "method": "POST",
                "path": "/",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
                "server": ("localhost", 8000),
                "scheme": "http",
                "root_path": "",
            }
        )

        request = Request(scope, self._make_receive(b"{}"))
        form = await request.form()

        assert dict(form) == {}

    async def test_close(self, urlencoded_scope):
        request = Request(urlencoded_scope, self._make_receive(b"k=v"))
        await request.form()

        await request.close()

    async def test_close_without_form(self, urlencoded_scope):
        request = Request(urlencoded_scope, self._make_receive(b"k=v"))

        await request.close()


class TestCaseRequestIntegration:
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
