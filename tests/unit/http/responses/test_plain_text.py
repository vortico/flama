from flama.http.responses.plain_text import PlainTextResponse


class TestCasePlainTextResponse:
    async def test_call(self, asgi_scope, asgi_receive, asgi_send):
        response = PlainTextResponse(content="hello")

        await response(asgi_scope, asgi_receive, asgi_send)

        body_message = asgi_send.call_args_list[1][0][0]
        assert body_message["body"] == b"hello"

    def test_media_type(self):
        response = PlainTextResponse(content="hello")

        assert response.headers["content-type"] == "text/plain; charset=utf-8"
