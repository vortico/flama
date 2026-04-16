from unittest.mock import AsyncMock

import pytest

from flama.http.data_structures import MutableHeaders
from flama.http.responses.response import BufferedResponse, Response, StreamingResponse


class _Response(Response):
    """Minimal concrete subclass for testing Response mechanics."""

    async def _send_response(self, scope, receive, send):
        return None


class _BufferedResponse(BufferedResponse):
    """Minimal concrete subclass for testing BufferedResponse mechanics."""

    def render(self, content):
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return content.encode(self.charset)
        if isinstance(content, memoryview):
            return bytes(content)
        return content


class _StreamingResponse(StreamingResponse):
    """Minimal concrete subclass for testing BufferedResponse mechanics."""

    def encode(self, chunk):
        if isinstance(chunk, bytes):
            return chunk
        if isinstance(chunk, str):
            return chunk.encode(self.charset)
        if isinstance(chunk, memoryview):
            return bytes(chunk)
        return chunk


class TestCaseResponse:
    def test_headers(self):
        response = _Response(headers={"x-custom": "val"})

        assert response.headers == MutableHeaders({"x-custom": "val"})

    def test_raw_headers(self):
        response = _Response(headers={"x-custom": "val"})

        assert (b"x-custom", b"val") in response.raw_headers

    @pytest.mark.parametrize(
        ["media_type", "headers", "expected"],
        [
            pytest.param("text/plain", None, "text/plain; charset=utf-8", id="text"),
            pytest.param("application/octet-stream", None, "application/octet-stream", id="binary"),
            pytest.param("text/html", {"content-type": "text/xml"}, "text/xml", id="not_overridden"),
        ],
    )
    def test_media_type(self, media_type, headers, expected):
        response = _Response(media_type=media_type, headers=headers)

        assert response.headers["content-type"] == expected

    @pytest.mark.parametrize(
        ["kwargs", "expected_parts"],
        [
            pytest.param(
                {"key": "session", "value": "abc123"},
                ["session=abc123", "Path=/", "SameSite=Lax"],
                id="basic",
            ),
            pytest.param(
                {"key": "session", "value": "abc", "max_age": 3600, "secure": True, "httponly": True},
                ["session=abc", "Max-Age=3600", "Path=/", "Secure", "HttpOnly", "SameSite=Lax"],
                id="full_options",
            ),
            pytest.param(
                {"key": "session", "value": "abc", "domain": "example.com", "samesite": "strict"},
                ["session=abc", "Domain=example.com", "Path=/", "SameSite=Strict"],
                id="domain_and_samesite",
            ),
            pytest.param(
                {"key": "session", "value": "abc", "path": None, "samesite": None},
                ["session=abc"],
                id="minimal",
            ),
            pytest.param(
                {"key": "session", "value": "abc", "path": None, "samesite": None, "partitioned": True},
                ["session=abc", "Partitioned"],
                id="partitioned",
            ),
        ],
    )
    def test_set_cookie(self, kwargs, expected_parts):
        response = _Response()
        response.set_cookie(**kwargs)

        cookie_headers = [v for k, v in response.raw_headers if k == b"set-cookie"]
        assert len(cookie_headers) == 1
        cookie_value = cookie_headers[0].decode("latin-1")
        for part in expected_parts:
            assert part in cookie_value

    def test_delete_cookie(self):
        response = _Response()
        response.delete_cookie("session")

        cookie_headers = [v for k, v in response.raw_headers if k == b"set-cookie"]
        assert len(cookie_headers) == 1
        cookie_value = cookie_headers[0].decode("latin-1")
        assert "session=" in cookie_value
        assert "Max-Age=0" in cookie_value

    def test_is_abc(self):
        assert Response.__abstractmethods__ == frozenset({"_send_response"})

    @pytest.mark.parametrize(
        ["left", "right", "expected"],
        [
            pytest.param(_Response(status_code=200), _Response(status_code=200), True, id="equal"),
            pytest.param(_Response(status_code=200), _Response(status_code=400), False, id="different"),
        ],
    )
    def test_eq(self, left, right, expected):
        assert (left == right) == expected

    @pytest.mark.parametrize(
        ["left", "right", "expected"],
        [
            pytest.param(_Response(status_code=200), _Response(status_code=200), True, id="equal"),
            pytest.param(_Response(status_code=200), _Response(status_code=400), False, id="different"),
        ],
    )
    def test_hash(self, left, right, expected):
        assert (hash(left) == hash(right)) == expected


class TestCaseBufferedResponse:
    def test_is_abc(self):
        assert BufferedResponse.__abstractmethods__ == frozenset({"render"})

    def test_content_required(self):
        with pytest.raises(ValueError, match="Either 'content' or 'path' must be provided"):
            _BufferedResponse()

    def test_raw_headers(self):
        response = _BufferedResponse("foo")

        header = next((v for k, v in response.raw_headers if k == b"content-length"), None)
        assert header == b"3"

    @pytest.mark.parametrize(
        ["content", "status_code", "use_background"],
        [
            pytest.param("hello", 200, False, id="http"),
            pytest.param(b"", 200, True, id="background"),
        ],
    )
    async def test_call(self, content, status_code, use_background, asgi_scope, asgi_receive, asgi_send):
        background = AsyncMock() if use_background else None
        response = _BufferedResponse(content, status_code=status_code, background=background)

        await response(asgi_scope, asgi_receive, asgi_send)

        assert asgi_send.call_count == 2
        start_message = asgi_send.call_args_list[0][0][0]
        body_message = asgi_send.call_args_list[1][0][0]
        assert start_message["type"] == "http.response.start"
        assert start_message["status"] == status_code
        assert body_message["type"] == "http.response.body"
        assert body_message["body"] == response.body
        if use_background:
            background.assert_awaited_once()

    @pytest.mark.parametrize(
        ["content", "expected"],
        [
            pytest.param(b"raw", b"raw", id="bytes"),
            pytest.param("text", b"text", id="string"),
            pytest.param(memoryview(b"mem"), b"mem", id="memoryview"),
        ],
    )
    def test_render(self, content, expected):
        response = _BufferedResponse(content)

        assert response.body == expected

    @pytest.mark.parametrize(
        ["left", "right", "expected"],
        [
            pytest.param(_BufferedResponse(b"foo"), _BufferedResponse(b"foo"), True, id="equal"),
            pytest.param(_BufferedResponse(b"foo"), _BufferedResponse(b"bar"), False, id="different"),
        ],
    )
    def test_hash(self, left, right, expected):
        assert (hash(left) == hash(right)) == expected


class TestCaseStreamingResponse:
    def test_is_abc(self):
        assert StreamingResponse.__abstractmethods__ == frozenset({"encode"})

    def test_raw_headers(self):
        response = _StreamingResponse([1, 2, 3])

        assert not any(k == b"content-length" for k, _ in response.raw_headers)

    @pytest.mark.parametrize(
        ["content_type", "use_background", "expected_chunks"],
        [
            pytest.param("sync_bytes", False, [b"hello", b" ", b"world"], id="sync_bytes"),
            pytest.param("sync_str", False, [b"hello", b" ", b"world"], id="sync_str"),
            pytest.param("async_bytes", False, [b"async", b"data"], id="async_bytes"),
            pytest.param("sync_bytes", True, [b""], id="background"),
        ],
    )
    async def test_call(self, content_type, use_background, expected_chunks, asgi_scope, asgi_receive, asgi_send):
        if content_type == "sync_str":
            content = iter(["hello", " ", "world"])
        elif content_type == "async_bytes":

            async def _gen():
                yield b"async"
                yield b"data"

            content = _gen()
        elif use_background:
            content = iter([b""])
        else:
            content = iter([b"hello", b" ", b"world"])

        background = AsyncMock() if use_background else None
        response = _StreamingResponse(content, background=background)

        await response(asgi_scope, asgi_receive, asgi_send)

        start_message = asgi_send.call_args_list[0][0][0]
        assert start_message["type"] == "http.response.start"
        assert start_message["status"] == 200
        body_calls = [c[0][0] for c in asgi_send.call_args_list[1:]]
        for i, expected in enumerate(expected_chunks):
            assert body_calls[i]["body"] == expected
            assert body_calls[i]["more_body"] is True
        assert body_calls[len(expected_chunks)]["body"] == b""
        assert body_calls[len(expected_chunks)]["more_body"] is False
        if use_background:
            background.assert_awaited_once()

    async def test_oserror_during_stream(self, asgi_scope, asgi_receive, asgi_send):
        async def _gen():
            yield b"partial"
            raise OSError("Broken pipe")

        response = _StreamingResponse(_gen())

        await response(asgi_scope, asgi_receive, asgi_send)

        start_message = asgi_send.call_args_list[0][0][0]
        assert start_message["type"] == "http.response.start"
        assert start_message["status"] == 200

    async def test_oserror_suppresses_background(self, asgi_scope, asgi_receive, asgi_send):
        async def _gen():
            raise OSError("Connection reset")
            yield b""  # pragma: no cover

        background = AsyncMock()
        response = _StreamingResponse(_gen(), background=background)

        await response(asgi_scope, asgi_receive, asgi_send)

        background.assert_not_awaited()

    def test_hash(self):
        content = [1]

        assert hash(_StreamingResponse(content)) == hash(_StreamingResponse(content))
        assert hash(_StreamingResponse(content)) != hash(_StreamingResponse([1]))
