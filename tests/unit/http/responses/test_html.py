from flama.http.responses.html import HTMLResponse


class TestCaseHTMLResponse:
    async def test_call(self, asgi_scope, asgi_receive, asgi_send):
        response = HTMLResponse(content="<h1>Hello</h1>")

        await response(asgi_scope, asgi_receive, asgi_send)

        body_message = asgi_send.call_args_list[1][0][0]
        assert body_message["body"] == b"<h1>Hello</h1>"

    def test_media_type(self):
        response = HTMLResponse(content="<h1>Hello</h1>")

        assert response.headers["content-type"] == "text/html; charset=utf-8"
