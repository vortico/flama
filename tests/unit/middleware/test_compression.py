import gzip
from unittest.mock import AsyncMock

import pytest

from flama import Flama, types
from flama.client import Client
from flama.codecs import BrotliCodec, GzipCodec
from flama.http.responses.response import Response
from flama.http.responses.streaming import StreamingResponse
from flama.middleware.compression import CompressionMiddleware


class TestCaseCompressionMiddleware:
    @pytest.fixture(scope="function")
    def app(self, tmp_path):
        app = Flama(schema=None, docs=None, middleware=[CompressionMiddleware(minimum_size=500)])

        data_file = tmp_path / "stream.bin"
        data_file.write_bytes(b"x" * 1000)

        @app.route("/large/")
        def large():
            return {"data": "x" * 1000}

        @app.route("/small/")
        def small():
            return {"data": "tiny"}

        @app.route("/stream/")
        async def streaming():
            async def gen():
                yield b"x" * 600
                yield b"y" * 600

            return StreamingResponse(gen(), media_type="text/plain")

        @app.route("/sse/")
        def sse_skip():
            return Response(content=b"event: ping\ndata: x\n\n", media_type="text/event-stream")

        @app.route("/pre-encoded/")
        def pre_encoded():
            payload = gzip.compress(b"x" * 1000)
            return Response(
                content=payload,
                media_type="application/octet-stream",
                headers={"content-encoding": "gzip"},
            )

        @app.route("/file/")
        def large_file():
            from flama.http.responses.file import FileResponse

            return FileResponse(path=str(data_file))

        return app

    @pytest.mark.parametrize(
        ["path", "method", "request_headers", "status_code", "expected_encoding"],
        [
            pytest.param("/large/", "get", {"accept-encoding": "br"}, 200, "br", id="brotli"),
            pytest.param("/large/", "get", {"accept-encoding": "gzip"}, 200, "gzip", id="gzip"),
            pytest.param("/large/", "get", {"accept-encoding": "gzip, br"}, 200, "br", id="both_prefers_brotli"),
            pytest.param("/large/", "get", {"accept-encoding": "identity"}, 200, None, id="identity_no_compression"),
            pytest.param("/small/", "get", {"accept-encoding": "br"}, 200, None, id="small_body_below_threshold"),
            pytest.param("/stream/", "get", {"accept-encoding": "br"}, 200, "br", id="streaming"),
            pytest.param("/sse/", "get", {"accept-encoding": "br"}, 200, None, id="sse_skip"),
            pytest.param("/pre-encoded/", "get", {"accept-encoding": "br"}, 200, "gzip", id="pre_encoded_skip"),
            pytest.param("/file/", "get", {"accept-encoding": "br"}, 200, "br", id="file_streaming"),
        ],
    )
    async def test_request(self, client, path, method, request_headers, status_code, expected_encoding):
        response = await client.request(method, path, headers=request_headers)

        assert response.status_code == status_code

        assert response.headers.get("content-encoding", None) == expected_encoding

    async def test_non_body_message_flushes_buffered_start(self):
        async def inner_app(scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
            await send(
                types.Message(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [(b"content-type", b"text/plain"), (b"content-length", b"1000")],
                    }
                )
            )
            await send(types.Message({"type": "http.response.pathsend", "path": "/tmp/example.bin"}))

        middleware = CompressionMiddleware(minimum_size=500)._build(inner_app)
        sent: list[types.Message] = []

        async def capture_send(message: types.Message) -> None:
            sent.append(message)

        scope = types.Scope(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/",
                "raw_path": b"/",
                "root_path": "",
                "query_string": b"",
                "headers": [(b"accept-encoding", b"br")],
            }
        )

        await middleware(scope, AsyncMock(), capture_send)

        assert sent[0]["type"] == "http.response.start"
        assert sent[1]["type"] == "http.response.pathsend"

    async def test_non_body_message_without_start(self):
        """A non-body message arriving before http.response.start should be forwarded without flushing."""

        async def inner_app(scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
            await send(types.Message({"type": "http.response.zerocopysend"}))

        middleware = CompressionMiddleware(minimum_size=500)._build(inner_app)
        sent: list[types.Message] = []

        async def capture_send(message: types.Message) -> None:
            sent.append(message)

        scope = types.Scope(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/",
                "raw_path": b"/",
                "root_path": "",
                "query_string": b"",
                "headers": [(b"accept-encoding", b"br")],
            }
        )

        await middleware(scope, AsyncMock(), capture_send)

        assert len(sent) == 1
        assert sent[0]["type"] == "http.response.zerocopysend"

    async def test_gzip_first(self):
        app = Flama(
            schema=None,
            docs=None,
            middleware=[CompressionMiddleware(minimum_size=500, codecs=[GzipCodec(), BrotliCodec()])],
        )

        @app.route("/large/")
        def large():
            return {"data": "x" * 1000}

        async with Client(app=app) as c:
            response = await c.request("get", "/large/", headers={"accept-encoding": "gzip, br"})

        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"

    async def test_compression_same_as_original(self):
        """When compression produces the same bytes as the original, only Vary is added."""
        from flama.middleware.compression import CompressionMiddleware

        initial_message = {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain"), (b"content-length", b"5")],
        }
        body = b"hello"

        class IdentityCodec:
            encoding = "identity"

        CompressionMiddleware._patch_headers(initial_message, IdentityCodec(), body, body, False)

        from flama.http.data_structures import Headers

        headers = Headers(raw=initial_message["headers"])
        assert "content-encoding" not in headers
        assert "vary" in headers

    async def test_non_http_scope_passthrough(self):
        inner = AsyncMock()
        middleware = CompressionMiddleware(minimum_size=500)._build(inner)
        scope = types.Scope({"type": "websocket"})

        await middleware(scope, AsyncMock(), AsyncMock())

        inner.assert_awaited_once()
