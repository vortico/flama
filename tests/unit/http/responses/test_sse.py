from unittest.mock import AsyncMock

import pytest

from flama.http.responses.sse import ServerSentEvent, ServerSentEventResponse


class TestCaseServerSentEvent:
    @pytest.mark.parametrize(
        ["event", "expected"],
        [
            pytest.param(
                ServerSentEvent(data="hello"),
                b"data: hello\n\n",
                id="data_only",
            ),
            pytest.param(
                ServerSentEvent(data="hello", event="message"),
                b"event: message\ndata: hello\n\n",
                id="with_event",
            ),
            pytest.param(
                ServerSentEvent(data="hello", id="1"),
                b"id: 1\ndata: hello\n\n",
                id="with_id",
            ),
            pytest.param(
                ServerSentEvent(data="hello", retry=3000),
                b"retry: 3000\ndata: hello\n\n",
                id="with_retry",
            ),
            pytest.param(
                ServerSentEvent(data="hello", event="update", id="42", retry=5000),
                b"id: 42\nevent: update\nretry: 5000\ndata: hello\n\n",
                id="all_fields",
            ),
            pytest.param(
                ServerSentEvent(data="line1\nline2"),
                b"data: line1\ndata: line2\n\n",
                id="multiline_data",
            ),
        ],
    )
    def test_encode(self, event, expected):
        assert event.encode() == expected


class TestCaseServerSentEventResponse:
    @pytest.mark.parametrize(
        ["content_type", "use_background", "expected_chunks"],
        [
            pytest.param(
                "sync_str",
                False,
                [b"data: hello\n\n", b"data: world\n\n"],
                id="sync_str",
            ),
            pytest.param(
                "sync_event",
                False,
                [b"event: msg\ndata: hello\n\n"],
                id="sync_event",
            ),
            pytest.param(
                "async_str",
                False,
                [b"data: async\n\n", b"data: data\n\n"],
                id="async_str",
            ),
            pytest.param(
                "sync_str",
                True,
                [b"data: bg\n\n"],
                id="background",
            ),
        ],
    )
    async def test_call(self, content_type, use_background, expected_chunks, asgi_scope, asgi_receive, asgi_send):
        if content_type == "sync_str":
            if use_background:
                content = iter(["bg"])
            else:
                content = iter(["hello", "world"])
        elif content_type == "sync_event":
            content = iter([ServerSentEvent(data="hello", event="msg")])
        elif content_type == "async_str":

            async def _gen():
                yield "async"
                yield "data"

            content = _gen()
        else:
            content = iter([])

        background = AsyncMock() if use_background else None
        response = ServerSentEventResponse(content=content, background=background)

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

    def test_headers(self):
        response = ServerSentEventResponse(content=iter([]))

        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["connection"] == "keep-alive"
        assert "content-length" not in response.headers

    def test_custom_headers(self):
        response = ServerSentEventResponse(content=iter([]), headers={"x-custom": "value"})

        assert response.headers["x-custom"] == "value"
        assert response.headers["cache-control"] == "no-cache"

    def test_header_override(self):
        response = ServerSentEventResponse(content=iter([]), headers={"cache-control": "max-age=60"})

        assert response.headers["cache-control"] == "max-age=60"

    async def test_oserror_during_stream(self, asgi_scope, asgi_receive, asgi_send):
        async def _gen():
            yield "partial"
            raise OSError("Broken pipe")

        response = ServerSentEventResponse(content=_gen())

        await response(asgi_scope, asgi_receive, asgi_send)

        start_message = asgi_send.call_args_list[0][0][0]
        assert start_message["type"] == "http.response.start"
        assert start_message["status"] == 200

    async def test_oserror_suppresses_background(self, asgi_scope, asgi_receive, asgi_send):
        async def _gen():
            raise OSError("Connection reset")
            yield ""  # pragma: no cover

        background = AsyncMock()
        response = ServerSentEventResponse(content=_gen(), background=background)

        await response(asgi_scope, asgi_receive, asgi_send)

        background.assert_not_awaited()
