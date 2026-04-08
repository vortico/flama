import sys
from unittest.mock import AsyncMock

import pytest

from flama.http.data_structures import MutableHeaders
from flama.http.responses.response import Response


class TestCaseResponse:
    @pytest.mark.parametrize(
        ["content", "status_code", "scope_type", "use_background"],
        [
            pytest.param("hello", 200, "http", False, id="http"),
            pytest.param(b"", 200, "websocket", False, id="websocket"),
            pytest.param(b"", 200, "http", True, id="background"),
        ],
    )
    async def test_call(self, content, status_code, scope_type, use_background, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = scope_type
        background = AsyncMock() if use_background else None
        response = Response(content=content, status_code=status_code, background=background)
        prefix = "websocket." if scope_type == "websocket" else ""

        await response(asgi_scope, asgi_receive, asgi_send)

        assert asgi_send.call_count == 2
        start_message = asgi_send.call_args_list[0][0][0]
        body_message = asgi_send.call_args_list[1][0][0]
        assert start_message["type"] == f"{prefix}http.response.start"
        assert start_message["status"] == status_code
        assert body_message["type"] == f"{prefix}http.response.body"
        assert body_message["body"] == response.body
        if use_background:
            background.assert_awaited_once()

    @pytest.mark.parametrize(
        ["content", "expected"],
        [
            pytest.param(None, b"", id="none"),
            pytest.param(b"raw", b"raw", id="bytes"),
            pytest.param("text", b"text", id="string"),
            pytest.param(memoryview(b"mem"), b"mem", id="memoryview"),
        ],
    )
    def test_render(self, content, expected):
        response = Response(content=content)

        assert response.body == expected

    @pytest.mark.parametrize(
        ["content", "status_code", "headers", "expected_header", "expected_value"],
        [
            pytest.param("hello", 200, None, "content-length", "5", id="content_length"),
            pytest.param("hello", 200, {"x-custom": "value"}, "x-custom", "value", id="custom"),
            pytest.param("", 204, None, "content-length", None, id="no_content_length_204"),
            pytest.param("", 304, None, "content-length", None, id="no_content_length_304"),
        ],
    )
    def test_headers(self, content, status_code, headers, expected_header, expected_value):
        response = Response(content=content, status_code=status_code, headers=headers)

        assert isinstance(response.headers, MutableHeaders)
        if expected_value is None:
            assert expected_header not in response.headers
        else:
            assert response.headers[expected_header] == expected_value

    def test_raw_headers(self):
        response = Response(content="hi", headers={"x-custom": "val"})

        assert (b"x-custom", b"val") in response.raw_headers
        assert any(k == b"content-length" for k, _ in response.raw_headers)

    @pytest.mark.parametrize(
        ["media_type", "headers", "expected"],
        [
            pytest.param("text/plain", None, "text/plain; charset=utf-8", id="text"),
            pytest.param("application/octet-stream", None, "application/octet-stream", id="binary"),
            pytest.param("text/html", {"content-type": "text/xml"}, "text/xml", id="not_overridden"),
        ],
    )
    def test_media_type(self, media_type, headers, expected):
        response = Response(content="hello", media_type=media_type, headers=headers)

        assert response.headers["content-type"] == expected

    @pytest.mark.parametrize(
        ["kwargs", "expected_parts"],
        [
            pytest.param(
                {"key": "session", "value": "abc123"},
                ["session=abc123", "Path=/", "SameSite=lax"],
                id="basic",
            ),
            pytest.param(
                {"key": "session", "value": "abc", "max_age": 3600, "secure": True, "httponly": True},
                ["session=abc", "Max-Age=3600", "Path=/", "Secure", "HttpOnly", "SameSite=lax"],
                id="full_options",
            ),
            pytest.param(
                {"key": "session", "value": "abc", "domain": "example.com", "samesite": "strict"},
                ["session=abc", "Domain=example.com", "Path=/", "SameSite=strict"],
                id="domain_and_samesite",
            ),
            pytest.param(
                {"key": "session", "value": "abc", "path": None, "samesite": None},
                ["session=abc"],
                id="minimal",
            ),
        ],
    )
    def test_set_cookie(self, kwargs, expected_parts):
        response = Response(content="")
        response.set_cookie(**kwargs)

        cookie_headers = [v for k, v in response.raw_headers if k == b"set-cookie"]
        assert len(cookie_headers) == 1
        cookie_value = cookie_headers[0].decode("latin-1")
        for part in expected_parts:
            assert part in cookie_value

    def test_delete_cookie(self):
        response = Response(content="")
        response.delete_cookie("session")

        cookie_headers = [v for k, v in response.raw_headers if k == b"set-cookie"]
        assert len(cookie_headers) == 1
        cookie_value = cookie_headers[0].decode("latin-1")
        assert "session=" in cookie_value
        assert "Max-Age=0" in cookie_value

    @pytest.mark.parametrize(
        ["left", "right", "expected"],
        [
            pytest.param(Response(content="foo"), Response(content="foo"), True, id="equal"),
            pytest.param(Response(content="foo"), Response(content="bar"), False, id="different"),
        ],
    )
    def test_eq(self, left, right, expected):
        assert (left == right) == expected

    @pytest.mark.parametrize(
        ["left", "right", "expected"],
        [
            pytest.param(Response(content="foo"), Response(content="foo"), True, id="equal"),
            pytest.param(Response(content="foo"), Response(content="bar"), False, id="different"),
        ],
    )
    def test_hash(self, left, right, expected):
        assert (hash(left) == hash(right)) == expected

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="partitioned supported natively")
    def test_set_cookie_partitioned_unsupported(self):
        response = Response(content="")

        with pytest.raises(ValueError, match="Partitioned cookies"):
            response.set_cookie("session", "abc", partitioned=True)
