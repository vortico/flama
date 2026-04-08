from unittest.mock import AsyncMock

import pytest

from flama.http.responses.streaming import StreamingResponse


class TestCaseStreamingResponse:
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
        response = StreamingResponse(content=content, background=background)

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

    def test_media_type(self):
        response = StreamingResponse(content=iter([]), media_type="text/event-stream")

        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    def test_headers(self):
        response = StreamingResponse(content=iter([]), headers={"x-custom": "value"})

        assert response.headers["x-custom"] == "value"

    def test_no_content_length(self):
        response = StreamingResponse(content=iter([b"data"]))

        assert "content-length" not in response.headers

    async def test_oserror_during_stream(self, asgi_scope, asgi_receive, asgi_send):
        async def _gen():
            yield b"partial"
            raise OSError("Broken pipe")

        response = StreamingResponse(content=_gen())

        await response(asgi_scope, asgi_receive, asgi_send)

        start_message = asgi_send.call_args_list[0][0][0]
        assert start_message["type"] == "http.response.start"
        assert start_message["status"] == 200

    async def test_oserror_suppresses_background(self, asgi_scope, asgi_receive, asgi_send):
        async def _gen():
            raise OSError("Connection reset")
            yield b""  # pragma: no cover

        background = AsyncMock()
        response = StreamingResponse(content=_gen(), background=background)

        await response(asgi_scope, asgi_receive, asgi_send)

        background.assert_not_awaited()
